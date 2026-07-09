import tempfile
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import cv2
import numpy as np

from backend.app.services.image_compare_service import ImageCompareRuntimeError, ImageCompareService
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


class ImageCompareServiceTests(unittest.TestCase):
    def test_default_status_uses_opencv_when_no_model_selected(self):
        with TemporaryDirectory() as runtime_dir, TemporaryDirectory() as bundle_dir:
            runtime_root = Path(runtime_dir)
            bundle_root = Path(bundle_dir)

            with mock.patch("backend.app.services.image_compare_service.settings.WORKING_DIR", runtime_root), \
                 mock.patch("backend.app.services.image_compare_service.settings.BUNDLE_DIR", bundle_root), \
                 mock.patch("backend.app.services.image_compare_service.settings.IMAGE_MODELS_DIR", runtime_root / "image_models"):
                service = ImageCompareService()

            status = service.get_status()

        self.assertEqual(status["compare_backend"], "opencv")
        self.assertIsNone(status["active_model"])
        self.assertEqual(status["recommended_model"]["name"], "DINOv2-Base")

    def test_selected_model_must_be_explicitly_cleared_to_return_to_opencv(self):
        with TemporaryDirectory() as runtime_dir, TemporaryDirectory() as bundle_dir:
            runtime_root = Path(runtime_dir)
            bundle_root = Path(bundle_dir)

            with mock.patch("backend.app.services.image_compare_service.settings.WORKING_DIR", runtime_root), \
                 mock.patch("backend.app.services.image_compare_service.settings.BUNDLE_DIR", bundle_root), \
                 mock.patch("backend.app.services.image_compare_service.settings.IMAGE_MODELS_DIR", runtime_root / "image_models"):
                service = ImageCompareService()

            model_dir = runtime_root / "image_models" / "DINOv2-Base"
            model_dir.mkdir(parents=True, exist_ok=True)
            (model_dir / "config.json").write_text("{}", encoding="utf-8")
            (model_dir / "model.safetensors").write_bytes(b"weights")

            service.set_active_model("DINOv2-Base")
            self.assertEqual(service.get_status()["compare_backend"], "dinov2")

            cleared = service.clear_active_model()

        self.assertEqual(cleared["compare_backend"], "opencv")
        self.assertIsNone(cleared["active_model"])

    def test_verify_uses_opencv_when_no_model_selected(self):
        service = ImageCompareService()

        with mock.patch.object(service, "get_active_model", return_value=None), \
             mock.patch.object(service, "_verify_with_opencv_path", return_value={"success": True, "engine": "opencv"}) as verify_opencv:
            result = service.verify("screen.png", "icon.png")

        verify_opencv.assert_called_once_with("screen.png", "icon.png", 0.9)
        self.assertEqual(result["engine"], "opencv")

    def test_verify_uses_dinov2_when_model_selected(self):
        service = ImageCompareService()
        fake_image = np.zeros((32, 32, 3), dtype=np.uint8)

        with mock.patch.object(service, "get_active_model", return_value={"name": "DINOv2-Base"}), \
             mock.patch("backend.app.services.image_compare_service.cv2.imread", side_effect=[fake_image, fake_image]), \
             mock.patch.object(service, "_verify_with_dinov2_arrays", return_value={"success": True, "engine": "dinov2", "model_name": "DINOv2-Base"}) as verify_dino:
            result = service.verify("screen.png", "icon.png")

        verify_dino.assert_called_once()
        self.assertEqual(result["engine"], "dinov2")

    def test_download_model_retries_hf_mirror_after_primary_endpoint_failure(self):
        with TemporaryDirectory() as runtime_dir, TemporaryDirectory() as bundle_dir:
            runtime_root = Path(runtime_dir)
            bundle_root = Path(bundle_dir)

            with mock.patch("backend.app.services.image_compare_service.settings.WORKING_DIR", runtime_root), \
                 mock.patch("backend.app.services.image_compare_service.settings.BUNDLE_DIR", bundle_root), \
                 mock.patch("backend.app.services.image_compare_service.settings.IMAGE_MODELS_DIR", runtime_root / "image_models"):
                service = ImageCompareService()

            call_endpoints = []

            def fake_snapshot_download(**kwargs):
                call_endpoints.append(kwargs.get("endpoint"))
                target_dir = Path(kwargs["local_dir"])
                if len(call_endpoints) == 1:
                    raise RuntimeError("offline")
                target_dir.mkdir(parents=True, exist_ok=True)
                (target_dir / "config.json").write_text("{}", encoding="utf-8")
                (target_dir / "model.safetensors").write_bytes(b"weights")
                return str(target_dir)

            with mock.patch.object(service, "get_runtime_dependency_status", return_value={"missing": []}), \
                 mock.patch("huggingface_hub.snapshot_download", side_effect=fake_snapshot_download):
                result = service.download_model()

        self.assertEqual(call_endpoints[0], "https://hf-mirror.com")
        self.assertEqual(call_endpoints[1], "https://huggingface.co")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["model_name"], "DINOv2-Base")

    def test_download_model_raises_actionable_message_after_all_endpoints_fail(self):
        with TemporaryDirectory() as runtime_dir, TemporaryDirectory() as bundle_dir:
            runtime_root = Path(runtime_dir)
            bundle_root = Path(bundle_dir)

            with mock.patch("backend.app.services.image_compare_service.settings.WORKING_DIR", runtime_root), \
                 mock.patch("backend.app.services.image_compare_service.settings.BUNDLE_DIR", bundle_root), \
                 mock.patch("backend.app.services.image_compare_service.settings.IMAGE_MODELS_DIR", runtime_root / "image_models"):
                service = ImageCompareService()

            with mock.patch.object(service, "get_runtime_dependency_status", return_value={"missing": []}), \
                 mock.patch("huggingface_hub.snapshot_download", side_effect=RuntimeError("network unavailable")):
                with self.assertRaises(ImageCompareRuntimeError) as context:
                    service.download_model()

        message = str(context.exception)
        self.assertIn("HF_ENDPOINT", message)
        self.assertIn("https://hf-mirror.com", message)
        self.assertIn("facebook/dinov2-base", message)


if __name__ == "__main__":
    unittest.main()