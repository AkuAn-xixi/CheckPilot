import tempfile
import unittest
from pathlib import Path

import cv2

from backend.app.services.image_service import verify_image_match


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