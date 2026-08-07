import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cv2
import numpy as np

from backend.app.services.image_service import (
    ImageVerifier,
    _load_verify_config,
    verify_image_match,
)


class FeatureSimilarityTests(unittest.TestCase):
    def test_low_texture_returns_none(self):
        flat1 = np.full((100, 100, 3), 128, dtype=np.uint8)
        flat2 = np.full((100, 100, 3), 128, dtype=np.uint8)
        self.assertIsNone(ImageVerifier.calc_feature_similarity(flat1, flat2))

    def test_textured_returns_score(self):
        rng = np.random.default_rng(42)
        noise = rng.integers(0, 256, (120, 120, 3), dtype=np.uint8)
        score = ImageVerifier.calc_feature_similarity(noise, noise)
        self.assertIsNotNone(score)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


class ColorVerifyConfigTests(unittest.TestCase):
    def test_returns_defaults_when_no_config(self):
        with mock.patch("backend.app.services.image_service.settings") as mock_settings:
            mock_settings.CUSTOMIZATION_FILE = Path(tempfile.gettempdir()) / "missing_customization.json"
            cfg = _load_verify_config()
        self.assertEqual(cfg, {
            "color_min_similarity": 0.4,
            "color_weight": 0.2,
            "feature_min_similarity": 0.3,
        })

    def test_reads_custom_values(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_file = Path(tmp_dir) / "customization.json"
            cfg_file.write_text(json.dumps({
                "color_min_similarity": 0.6,
                "color_weight": 0.3,
                "feature_min_similarity": 0.5,
            }), encoding="utf-8")
            with mock.patch("backend.app.services.image_service.settings") as mock_settings:
                mock_settings.CUSTOMIZATION_FILE = cfg_file
                cfg = _load_verify_config()
        self.assertEqual(cfg, {
            "color_min_similarity": 0.6,
            "color_weight": 0.3,
            "feature_min_similarity": 0.5,
        })

    def test_clamps_invalid_values_to_defaults(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_file = Path(tmp_dir) / "customization.json"
            cfg_file.write_text(json.dumps({
                "color_min_similarity": 3.0,
                "color_weight": "bad",
                "feature_min_similarity": -1,
            }), encoding="utf-8")
            with mock.patch("backend.app.services.image_service.settings") as mock_settings:
                mock_settings.CUSTOMIZATION_FILE = cfg_file
                cfg = _load_verify_config()
        self.assertEqual(cfg, {
            "color_min_similarity": 0.4,
            "color_weight": 0.2,
            "feature_min_similarity": 0.3,
        })


class ImageVerifierTests(unittest.TestCase):
    def test_verify_image_match_requires_score_above_ninety_percent(self):
        screenshot_path = Path(__file__).resolve().parents[2] / "screenshots" / "SETTING-578.png"
        screenshot = cv2.imread(str(screenshot_path))

        self.assertIsNotNone(screenshot)

        icon_crop = screenshot[78:170, 1730:1845]
        padded_reference = cv2.copyMakeBorder(
            icon_crop,
            20,
            20,
            20,
            20,
            cv2.BORDER_CONSTANT,
            value=(255, 255, 255),
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_dir = Path(tmp_dir)
            screenshot_file = temp_dir / "screen.png"
            reference_file = temp_dir / "reference.png"
            cv2.imwrite(str(screenshot_file), screenshot)
            cv2.imwrite(str(reference_file), padded_reference)

            result = verify_image_match(str(screenshot_file), str(reference_file))

        self.assertTrue(result["success"])
        self.assertFalse(result["matched"])
        self.assertLess(result["score"], 0.9)
        self.assertGreaterEqual(result["color_score"], 0.95)

    def test_verify_image_match_accepts_exact_reference_above_ninety_percent(self):
        screenshot_path = Path(__file__).resolve().parents[2] / "screenshots" / "SETTING-578.png"
        screenshot = cv2.imread(str(screenshot_path))

        self.assertIsNotNone(screenshot)

        exact_reference = screenshot[78:170, 1730:1845]

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_dir = Path(tmp_dir)
            screenshot_file = temp_dir / "screen.png"
            reference_file = temp_dir / "reference.png"
            cv2.imwrite(str(screenshot_file), screenshot)
            cv2.imwrite(str(reference_file), exact_reference)

            result = verify_image_match(str(screenshot_file), str(reference_file))

        self.assertTrue(result["success"])
        self.assertTrue(result["matched"])
        self.assertGreaterEqual(result["score"], 0.9)
        self.assertGreaterEqual(result["template_score"], 0.9)


if __name__ == "__main__":
    unittest.main()
