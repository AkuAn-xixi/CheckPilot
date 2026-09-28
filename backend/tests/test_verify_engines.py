"""图片校验引擎分派与配置归一化测试。

用合成图，不依赖 ``screenshots/`` 下的真实样本（该目录被 gitignore）。
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cv2
import numpy as np

from backend.app.models.verify_config import (
    DEFAULT_AIRTEXT_STRATEGY,
    DEFAULT_AIRTEXT_THRESHOLD,
    ENGINE_AIRTEXT,
    ENGINE_OPENCV,
    VerifyConfig,
    normalize_verify_config,
)
from backend.app.services.image_service import verify_image_match
from backend.app.services.verify_engines import build_engine
from backend.app.utils.airtest_matcher.models import (
    DEFAULT_STRATEGY as KERNEL_DEFAULT_STRATEGY,
)
from backend.app.utils.airtest_matcher.models import (
    DEFAULT_THRESHOLD as KERNEL_DEFAULT_THRESHOLD,
)

_PATCH_SIZE = 60
_TARGET_LEFT = 300
_TARGET_TOP = 200
_COORD_TOLERANCE = 2


def _write_config(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _make_images(tmp_dir: Path) -> tuple[str, str, int, int]:
    """生成截图与参考图文件，返回 (截图路径, 参考图路径, 左, 上)。"""
    rng = np.random.default_rng(99)
    screen = np.zeros((480, 640, 3), dtype=np.uint8)
    screen[:, :, :] = np.linspace(40, 200, 640, dtype=np.uint8)[None, :, None]
    patch = rng.integers(0, 256, (_PATCH_SIZE, _PATCH_SIZE, 3), dtype=np.uint8)
    screen[_TARGET_TOP : _TARGET_TOP + _PATCH_SIZE, _TARGET_LEFT : _TARGET_LEFT + _PATCH_SIZE] = patch

    screen_file = tmp_dir / "screen.png"
    reference_file = tmp_dir / "reference.png"
    cv2.imwrite(str(screen_file), screen)
    cv2.imwrite(str(reference_file), patch)
    return str(screen_file), str(reference_file), _TARGET_LEFT, _TARGET_TOP


class VerifyConfigDefaultsTests(unittest.TestCase):
    def test_kernel_defaults_match_config_defaults(self):
        """漂移守卫：配置层与移植内核的默认值必须一致。

        两侧刻意不互相 import（models 层不能拖入 utils 的 adb_controller 依赖），
        所以用这个测试把「单一口径」钉住。
        """
        self.assertEqual(DEFAULT_AIRTEXT_STRATEGY, KERNEL_DEFAULT_STRATEGY)
        self.assertEqual(DEFAULT_AIRTEXT_THRESHOLD, KERNEL_DEFAULT_THRESHOLD)

    def test_normalize_verify_config_falls_back_on_invalid_values(self):
        """全部字段非法时逐项回落默认值，不抛异常。"""
        config = normalize_verify_config({
            "verify_engine": "tensorflow",
            "color_min_similarity": 8,
            "color_weight": None,
            "feature_min_similarity": "abc",
            "airtest_threshold": -3,
            "airtest_rgb": "yes",
            "airtest_strategy": "brisk",
        })

        self.assertEqual(config, VerifyConfig())

    def test_normalize_verify_config_accepts_valid_values(self):
        config = normalize_verify_config({
            "verify_engine": ENGINE_AIRTEXT,
            "airtest_threshold": 0.9,
            "airtest_rgb": True,
            "airtest_strategy": "mstpl",
        })

        self.assertEqual(config.verify_engine, ENGINE_AIRTEXT)
        self.assertEqual(config.airtest_threshold, 0.9)
        self.assertTrue(config.airtest_rgb)
        self.assertEqual(config.airtest_strategy, "mstpl")


class BuildEngineTests(unittest.TestCase):
    def test_unknown_engine_falls_back_to_opencv(self):
        engine = build_engine("tensorflow", VerifyConfig())

        self.assertEqual(engine.name, ENGINE_OPENCV)

    def test_airtest_engine_is_constructed_by_name(self):
        engine = build_engine(ENGINE_AIRTEXT, VerifyConfig())

        self.assertEqual(engine.name, ENGINE_AIRTEXT)


class EngineDispatchTests(unittest.TestCase):
    """经 verify_image_match 走完整分派链（含读盘配置）。"""

    def _verify_with_config(self, payload: dict):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            screen_file, reference_file, left, top = _make_images(tmp_path)
            cfg_file = tmp_path / "customization.json"
            _write_config(cfg_file, payload)
            with mock.patch("backend.app.services.image_service.settings") as mock_settings:
                mock_settings.CUSTOMIZATION_FILE = cfg_file
                result = verify_image_match(screen_file, reference_file)
        return result, left, top

    def test_airtest_engine_returns_coordinates_and_engine_name(self):
        """切到 airtest 后：结果带引擎名与匹配坐标，且不含伪造的四路分数。"""
        result, left, top = self._verify_with_config({"verify_engine": ENGINE_AIRTEXT})

        self.assertTrue(result["success"])
        self.assertTrue(result["matched"])
        self.assertEqual(result["engine"], ENGINE_AIRTEXT)
        self.assertAlmostEqual(result["match_rect_x"], left, delta=_COORD_TOLERANCE)
        self.assertAlmostEqual(result["match_rect_y"], top, delta=_COORD_TOLERANCE)
        # airtest 不产出这些信号，缺键好过编造可比性存疑的数字
        for absent in ("template_score", "structure_score", "color_score", "feature_score"):
            self.assertNotIn(absent, result)

    def test_airtest_engine_uses_its_own_threshold_not_request_threshold(self):
        """airtest 阈值独立：与请求级 match_threshold 无关。"""
        result, _, _ = self._verify_with_config({
            "verify_engine": ENGINE_AIRTEXT,
            "airtest_threshold": 0.99,
        })

        self.assertGreaterEqual(result["score"], 0.99)
        self.assertTrue(result["matched"])
        self.assertAlmostEqual(result["airtest_threshold"], 0.99)

    def test_default_engine_is_opencv_and_keeps_existing_result_shape(self):
        """默认（配置无引擎键）仍走 opencv，既有结果结构不变。"""
        result, _, _ = self._verify_with_config({})

        self.assertTrue(result["success"])
        self.assertNotIn("engine", result)
        self.assertIn("template_score", result)
        self.assertIn("color_score", result)

    def test_explicit_opencv_engine_keeps_existing_result_shape(self):
        result, _, _ = self._verify_with_config({"verify_engine": ENGINE_OPENCV})

        self.assertTrue(result["success"])
        self.assertIn("template_score", result)
        self.assertNotIn("match_rect_x", result)

    def test_flat_reference_image_fails_on_both_engines(self):
        """纯色参考图：两个引擎必须给出同样的「未命中」，否则切引擎会翻转用例结论。

        纯色模板不含位置信息，airtest 侧若报命中就会写出无意义的坐标；opencv 侧
        实测对纯黑/纯白/纯灰一律 matched=False。
        """
        verdicts = {}
        for engine in (ENGINE_OPENCV, ENGINE_AIRTEXT):
            result, _, _ = self._verify_flat_with_config({"verify_engine": engine})
            verdicts[engine] = result["matched"]

        self.assertEqual(verdicts, {ENGINE_OPENCV: False, ENGINE_AIRTEXT: False})

    def _verify_flat_with_config(self, payload: dict):
        """同 _verify_with_config，但参考图是与屏上色块同色的纯色图。"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            screen = np.zeros((480, 640, 3), dtype=np.uint8)
            screen[:, :, :] = np.linspace(40, 200, 640, dtype=np.uint8)[None, :, None]
            flat = np.full((_PATCH_SIZE, _PATCH_SIZE, 3), 200, dtype=np.uint8)
            screen[
                _TARGET_TOP : _TARGET_TOP + _PATCH_SIZE, _TARGET_LEFT : _TARGET_LEFT + _PATCH_SIZE
            ] = flat
            screen_file, reference_file = tmp_path / "screen.png", tmp_path / "reference.png"
            cv2.imwrite(str(screen_file), screen)
            cv2.imwrite(str(reference_file), flat)

            cfg_file = tmp_path / "customization.json"
            _write_config(cfg_file, payload)
            with mock.patch("backend.app.services.image_service.settings") as mock_settings:
                mock_settings.CUSTOMIZATION_FILE = cfg_file
                result = verify_image_match(str(screen_file), str(reference_file))
        return result, _TARGET_LEFT, _TARGET_TOP


if __name__ == "__main__":
    unittest.main()
