import asyncio
import base64
import tempfile
import unittest
from collections.abc import AsyncIterator
from pathlib import Path
from unittest import mock

from fastapi import HTTPException

from backend.app.api import devices
from backend.app.models.schemas import DevicePreviewSaveRequest


class FakeController:
    def __init__(self, screenshot_path=None):
        self.screenshot_path = screenshot_path
        self.calls = []

    def take_screenshot(self, title=None):
        self.calls.append(title)
        return self.screenshot_path


class DevicePreviewTests(unittest.TestCase):
    def test_get_device_preview_returns_latest_screenshot_url(self):
        controller = FakeController(r"D:\Project\Check\screenshots\device_preview_device-123.png")

        with mock.patch("backend.app.api.devices.get_current_device_state", return_value="device-123"), mock.patch(
            "backend.app.api.devices.get_controller", return_value=controller
        ):
            result = asyncio.run(devices.get_device_preview())

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["device"], "device-123")
        self.assertEqual(controller.calls, ["device_preview_device-123"])
        self.assertTrue(result["screenshot_url"].startswith("/api/screenshot/device_preview_device-123.png?ts="))
        self.assertIsInstance(result["captured_at"], int)

    def test_get_device_preview_requires_selected_device(self):
        with mock.patch("backend.app.api.devices.get_current_device_state", return_value=None):
            with self.assertRaises(HTTPException) as context:
                asyncio.run(devices.get_device_preview())

        self.assertEqual(context.exception.status_code, 400)

    def test_get_device_preview_raises_when_screenshot_fails(self):
        controller = FakeController(None)

        with mock.patch("backend.app.api.devices.get_current_device_state", return_value="device-123"), mock.patch(
            "backend.app.api.devices.get_controller", return_value=controller
        ):
            with self.assertRaises(HTTPException) as context:
                asyncio.run(devices.get_device_preview())

        self.assertEqual(context.exception.status_code, 502)
        self.assertEqual(controller.calls, ["device_preview_device-123"])

    def test_get_device_preview_supports_capture_card_source(self):
        with mock.patch(
            "backend.app.api.devices.capture_card_service.capture_preview",
            return_value={
                "path": r"D:\Project\Check\screenshots\device_preview_capture_card_1.png",
                "captured_at": 123456789,
                "label": "采集卡 1",
                "device_id": 1,
            },
        ) as capture_preview:
            result = asyncio.run(devices.get_device_preview(devices.PREVIEW_SOURCE_CAPTURE_CARD))

        capture_preview.assert_called_once_with()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["preview_source"], devices.PREVIEW_SOURCE_CAPTURE_CARD)
        self.assertEqual(result["preview_label"], "采集卡 1")
        self.assertEqual(result["device"], "")
        self.assertEqual(result["captured_at"], 123456789)
        self.assertTrue(result["screenshot_url"].startswith("/api/screenshot/device_preview_capture_card_1.png?ts="))

    def test_get_device_preview_rejects_invalid_source(self):
        with self.assertRaises(HTTPException) as context:
            asyncio.run(devices.get_device_preview("invalid-source"))

        self.assertEqual(context.exception.status_code, 400)

    def test_get_device_preview_stream_returns_mjpeg_response_for_capture_card(self):
        with mock.patch(
            "backend.app.api.devices.capture_card_service.capture_encoded_frame",
            side_effect=[
                {"bytes": b"jpeg-one", "captured_at": 1, "label": "采集卡 1", "device_id": 1},
                RuntimeError("stop stream"),
            ],
        ) as capture_frame:
            response = asyncio.run(devices.get_device_preview_stream())

            async def read_first_chunk(iterator: AsyncIterator[bytes]) -> bytes:
                return await iterator.__anext__()

            first_chunk = asyncio.run(read_first_chunk(response.body_iterator))

        capture_frame.assert_called()
        self.assertEqual(response.media_type, "multipart/x-mixed-replace; boundary=frame")
        self.assertIn(b"Content-Type: image/jpeg", first_chunk)
        self.assertIn(b"jpeg-one", first_chunk)

    def test_get_device_preview_stream_rejects_adb_source(self):
        with self.assertRaises(HTTPException) as context:
            asyncio.run(devices.get_device_preview_stream(devices.PREVIEW_SOURCE_ADB))

        self.assertEqual(context.exception.status_code, 400)

    def test_save_device_preview_writes_file_to_custom_directory(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            custom_dir = Path(tmp_dir) / 'captures'
            payload = DevicePreviewSaveRequest(
                image_base64=base64.b64encode(b'preview-bytes').decode('ascii'),
                file_name='CASE-5001.png',
                save_dir=str(custom_dir),
            )

            result = asyncio.run(devices.save_device_preview(payload))

            saved_path = custom_dir / 'CASE-5001.png'
            self.assertEqual(result['status'], 'success')
            self.assertEqual(result['file_name'], 'CASE-5001.png')
            self.assertEqual(result['saved_path'], str(saved_path))
            self.assertEqual(result['image_ref'], str(saved_path))
            self.assertEqual(saved_path.read_bytes(), b'preview-bytes')

    def test_save_device_preview_uses_unique_name_in_default_image_dir(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            image_dir = Path(tmp_dir) / 'images'
            image_dir.mkdir(parents=True, exist_ok=True)
            (image_dir / 'CASE-42.png').write_bytes(b'existing')

            payload = DevicePreviewSaveRequest(
                image_base64=base64.b64encode(b'new-preview').decode('ascii'),
                file_name='CASE-42.png',
            )

            with mock.patch('backend.app.api.devices.get_image_dir', return_value=image_dir):
                result = asyncio.run(devices.save_device_preview(payload))

            saved_path = image_dir / 'CASE-42-1.png'
            self.assertEqual(result['file_name'], 'CASE-42-1.png')
            self.assertEqual(result['image_ref'], 'CASE-42-1.png')
            self.assertEqual(saved_path.read_bytes(), b'new-preview')


if __name__ == "__main__":
    unittest.main()