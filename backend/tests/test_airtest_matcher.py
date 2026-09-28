"""airtest 匹配内核（utils/airtest_matcher）单元测试。

全部使用合成图像，不依赖 ``screenshots/`` 下的真实样本（该目录被 gitignore，
CI 与本地都可能不存在）。坐标容差取 ±2px：实测「形状 + 留白」场景会给出偏
1px 的位置，属于 TM_CCOEFF_NORMED 的正常抖动。
"""

import unittest

import cv2
import numpy as np

from backend.app.utils.airtest_matcher import (
    MatchOptions,
    MatchOutcome,
    match_template,
)

_SCREEN_HEIGHT = 480
_SCREEN_WIDTH = 640
# 手机分辨率，用于界定 mstpl 的可用范围与耗时
_PHONE_HEIGHT = 2340
_PHONE_WIDTH = 1080
_PATCH_SIZE = 60
_TARGET_LEFT = 300
_TARGET_TOP = 200
# 合成模板用固定种子，保证每次运行的可复现性
_RANDOM_SEED = 20240501
_COORD_TOLERANCE = 2

_OPTIONS = MatchOptions(threshold=0.85)


def _textured_patch(size: int) -> np.ndarray:
    """生成一块高纹理方图（纯色图无特征，匹配位置不唯一）。"""
    rng = np.random.default_rng(_RANDOM_SEED)
    return rng.integers(0, 256, (size, size, 3), dtype=np.uint8)


def _screen_with_patch(patch: np.ndarray, left: int, top: int) -> np.ndarray:
    """把模板贴到纯色底图上，底图带渐变以避免整幅同色。"""
    screen = np.zeros((_SCREEN_HEIGHT, _SCREEN_WIDTH, 3), dtype=np.uint8)
    gradient = np.linspace(40, 200, _SCREEN_WIDTH, dtype=np.uint8)
    screen[:, :, :] = gradient[None, :, None]
    height, width = patch.shape[:2]
    screen[top : top + height, left : left + width] = patch
    return screen


def _phone_screen_with_button() -> np.ndarray:
    """构造一张手机分辨率截图，含一块低频的按钮区域。

    mstpl 只对低频内容可靠（高频纹理在不同缩放比下相关性会被重采样打散），
    故用它来界定 mstpl 的可用范围。
    """
    screen = np.full((_PHONE_HEIGHT, _PHONE_WIDTH, 3), 240, dtype=np.uint8)
    cv2.rectangle(screen, (0, 0), (_PHONE_WIDTH, 160), (60, 60, 60), -1)
    cv2.putText(
        screen, "CheckPilot", (40, 110), cv2.FONT_HERSHEY_SIMPLEX, 2.2, (255, 255, 255), 5
    )
    cv2.rectangle(screen, (60, 300), (_PHONE_WIDTH - 60, 420), (200, 190, 170), -1)
    cv2.putText(
        screen, "START TEST", (140, 380), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (30, 30, 30), 4
    )
    return screen


class AirtestMatcherTests(unittest.TestCase):
    def test_match_template_known_patch_returns_expected_rect(self):
        """已知位置的纹理块：命中且矩形左上角与预期一致。"""
        patch = _textured_patch(_PATCH_SIZE)
        screen = _screen_with_patch(patch, _TARGET_LEFT, _TARGET_TOP)

        outcome = match_template(screen, patch, _OPTIONS)

        self.assertTrue(outcome.matched, outcome.message)
        self.assertGreaterEqual(outcome.confidence, 0.99)
        self.assertIsNotNone(outcome.rect)
        self.assertAlmostEqual(outcome.rect[0], _TARGET_LEFT, delta=_COORD_TOLERANCE)
        self.assertAlmostEqual(outcome.rect[1], _TARGET_TOP, delta=_COORD_TOLERANCE)
        self.assertAlmostEqual(outcome.rect[2], _PATCH_SIZE, delta=_COORD_TOLERANCE)

    def test_match_template_cropped_from_screen_hits(self):
        """从截图裁下来的模板必须命中（真实用例的主要形态）。"""
        screen = _screen_with_patch(_textured_patch(_PATCH_SIZE), _TARGET_LEFT, _TARGET_TOP)
        cropped = screen[_TARGET_TOP : _TARGET_TOP + _PATCH_SIZE, _TARGET_LEFT : _TARGET_LEFT + _PATCH_SIZE]

        outcome = match_template(screen, cropped.copy(), _OPTIONS)

        self.assertTrue(outcome.matched, outcome.message)
        self.assertAlmostEqual(outcome.rect[0], _TARGET_LEFT, delta=_COORD_TOLERANCE)

    def test_match_template_unrelated_template_confidence_is_low(self):
        """无关模板：不命中，但给出真实分数供标定阈值。"""
        screen = _screen_with_patch(_textured_patch(_PATCH_SIZE), _TARGET_LEFT, _TARGET_TOP)
        unrelated = np.full((_PATCH_SIZE, _PATCH_SIZE, 3), 128, dtype=np.uint8)
        cv2.circle(unrelated, (_PATCH_SIZE // 2, _PATCH_SIZE // 2), 20, (255, 255, 255), -1)

        outcome = match_template(screen, unrelated, _OPTIONS)

        self.assertFalse(outcome.matched)
        self.assertLess(outcome.confidence, _OPTIONS.threshold)
        self.assertIn("未达到阈值", outcome.message)

    def test_match_template_flat_template_is_never_matched(self):
        """纯色模板一律判未命中，不得给出 (0, 0) 这种 TM_CCOEFF_NORMED 的假坐标。

        纯色模板位置本就不唯一，报「命中」等于把无意义的坐标写进报告；既有
        opencv 引擎对纯黑/纯白/纯灰模板实测也都返回 matched=False，这里保持一致，
        免得切换引擎后同一用例的结论翻转。纯黑是其中最容易漏的一种：
        ``TM_SQDIFF_NORMED`` 的分母含模板自身平方和，纯黑模板会让它退化成恒 1.0。
        """
        for color in ((0, 0, 0), (255, 255, 255), (200, 200, 200)):
            with self.subTest(color=color):
                patch = np.full((_PATCH_SIZE, _PATCH_SIZE, 3), color, dtype=np.uint8)
                screen = _screen_with_patch(patch, _TARGET_LEFT, _TARGET_TOP)

                outcome = match_template(screen, patch, _OPTIONS)

                self.assertFalse(outcome.matched, outcome.message)
                self.assertIsNone(outcome.rect)
                self.assertIn("纯色", outcome.message)

    def test_match_template_template_larger_than_screen_reports_failure(self):
        """模板大于截图：返回未命中结果而非抛异常。"""
        screen = np.zeros((40, 40, 3), dtype=np.uint8)
        oversized = _textured_patch(80)

        outcome = match_template(screen, oversized, _OPTIONS)

        self.assertFalse(outcome.matched)
        self.assertIn("大于截图", outcome.message)

    def test_match_template_rejects_empty_input(self):
        """空图：返回未命中并说明原因。"""
        outcome = match_template(np.zeros((0, 0, 3), dtype=np.uint8), _textured_patch(10))

        self.assertFalse(outcome.matched)
        self.assertIn("为空", outcome.message)

    def test_match_template_grayscale_input_is_accepted(self):
        """灰度输入自动扩成三通道后仍能命中。"""
        patch = _textured_patch(_PATCH_SIZE)
        screen = _screen_with_patch(patch, _TARGET_LEFT, _TARGET_TOP)
        screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        patch_gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)

        outcome = match_template(screen_gray, patch_gray, _OPTIONS)

        self.assertTrue(outcome.matched, outcome.message)
        self.assertAlmostEqual(outcome.rect[0], _TARGET_LEFT, delta=_COORD_TOLERANCE)

    def test_default_options_use_single_scale_strategy(self):
        """默认策略是 tpl：实测 mstpl 慢 30 倍且对高频模板会漏配。

        这是有意的取舍（见 models.DEFAULT_STRATEGY 的实测记录），
        若有人改回 mstpl，此测试会拦住。
        """
        self.assertEqual(MatchOptions().strategy, "tpl")
        self.assertEqual(MatchOptions().threshold, 0.85)
        self.assertFalse(MatchOptions().rgb)

    def test_match_template_multiscale_strategy_matches_ui_template(self):
        """mstpl 的可用范围：手机分辨率 + 低频 UI 模板（跨分辨率场景才需要它）。

        注意 mstpl 对本用例的定位存在 1-3px 偏差且耗时秒级，所以它不是默认策略。
        """
        screen = _phone_screen_with_button()
        template = screen[300:420, 60:1020].copy()

        outcome = match_template(screen, template, MatchOptions(strategy="mstpl"))

        self.assertTrue(outcome.matched, outcome.message)
        self.assertGreater(outcome.confidence, 0.9)
        self.assertAlmostEqual(outcome.rect[0], 60, delta=5)
        self.assertAlmostEqual(outcome.rect[1], 300, delta=5)

    def test_match_template_unknown_strategy_falls_back_to_default(self):
        """未知策略回落默认策略，且不抛异常。"""
        patch = _textured_patch(_PATCH_SIZE)
        screen = _screen_with_patch(patch, _TARGET_LEFT, _TARGET_TOP)

        outcome = match_template(screen, patch, MatchOptions(strategy="brisk"))

        self.assertTrue(outcome.matched, outcome.message)
        self.assertEqual(outcome.strategy, "brisk")  # 回落不篡改用户所见策略名

    def test_match_template_rgb_option_is_sensitive_to_color_but_gray_is_not(self):
        """rgb=True 走逐通道 HSV 置信度：图像结构相同但配色不同时分数显著下降。

        这印证了 airtest 的 confidence 语义随 rgb 变 —— 定位永远是灰度的，
        只有报出的分数不同，因此两个引擎的阈值不可互换。
        """
        patch = _textured_patch(_PATCH_SIZE)
        screen = _screen_with_patch(patch, _TARGET_LEFT, _TARGET_TOP)
        # 把目标区域的三通道顺序打乱：结构还是同一块纹理，但配色已不同
        region = screen[_TARGET_TOP : _TARGET_TOP + _PATCH_SIZE, _TARGET_LEFT : _TARGET_LEFT + _PATCH_SIZE]
        region[:] = region[:, :, ::-1]

        gray_outcome = match_template(screen, patch, MatchOptions(strategy="tpl", rgb=False))
        rgb_outcome = match_template(screen, patch, MatchOptions(strategy="tpl", rgb=True))

        # 灰度只认结构，配色被打乱也照样命中
        self.assertTrue(gray_outcome.matched, gray_outcome.message)
        self.assertGreater(gray_outcome.confidence, 0.9)
        # 逐通道比色则直接判为不匹配 —— 同一画面在两种模式下的结论相反，
        # 说明 airtest 的阈值不能沿用 opencv 引擎那一套
        self.assertLess(rgb_outcome.confidence, _OPTIONS.threshold)
        self.assertFalse(rgb_outcome.matched)

    def test_match_template_records_elapsed_time(self):
        """耗时字段有值，供性能观测使用。"""
        patch = _textured_patch(_PATCH_SIZE)
        screen = _screen_with_patch(patch, _TARGET_LEFT, _TARGET_TOP)

        outcome = match_template(screen, patch, _OPTIONS)

        self.assertIsInstance(outcome, MatchOutcome)
        self.assertGreater(outcome.elapsed_seconds, 0.0)


if __name__ == "__main__":
    unittest.main()
