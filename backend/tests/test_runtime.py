import unittest
import tempfile
from pathlib import Path
from unittest import mock

from backend.app import runtime


class FakeController:
    def __init__(self, devices):
        self.devices = devices
        self.device_serial = None

    def list_devices(self):
        return list(self.devices)

    def select_device(self, device_serial):
        self.device_serial = device_serial
        return True


class RuntimeCurrentDeviceTests(unittest.TestCase):
    def setUp(self):
        self.original_controller = runtime.runtime_state.controller
        self.original_current_device = runtime.runtime_state.current_device
        self.temp_dir = tempfile.TemporaryDirectory()
        self.runtime_state_file = Path(self.temp_dir.name) / "runtime_state.json"
        self.runtime_state_patch = mock.patch("backend.app.runtime.RUNTIME_STATE_FILE", self.runtime_state_file)
        self.runtime_state_patch.start()

    def tearDown(self):
        runtime.runtime_state.controller = self.original_controller
        runtime.runtime_state.current_device = self.original_current_device
        self.runtime_state_patch.stop()
        self.temp_dir.cleanup()

    def test_get_current_device_clears_stale_device_when_not_connected(self):
        fake_controller = FakeController([])
        runtime.runtime_state.controller = fake_controller
        runtime.runtime_state.current_device = "stale-device"

        with mock.patch("backend.app.runtime._get_main_module", return_value=None):
            self.assertIsNone(runtime.get_current_device())

        self.assertIsNone(runtime.runtime_state.current_device)
        self.assertIsNone(fake_controller.device_serial)

    def test_get_current_device_keeps_connected_device_selected(self):
        fake_controller = FakeController(["device-123"])
        runtime.runtime_state.controller = fake_controller
        runtime.runtime_state.current_device = "device-123"

        with mock.patch("backend.app.runtime._get_main_module", return_value=None):
            self.assertEqual(runtime.get_current_device(), "device-123")

        self.assertEqual(fake_controller.device_serial, "device-123")

    def test_get_current_device_restores_persisted_device(self):
        fake_controller = FakeController(["device-123"])
        runtime.runtime_state.controller = fake_controller
        runtime.runtime_state.current_device = None
        self.runtime_state_file.write_text('{"current_device": "device-123"}', encoding="utf-8")

        with mock.patch("backend.app.runtime._get_main_module", return_value=None):
            self.assertEqual(runtime.get_current_device(), "device-123")

        self.assertEqual(fake_controller.device_serial, "device-123")

    def test_get_current_device_clears_stale_persisted_device(self):
        fake_controller = FakeController([])
        runtime.runtime_state.controller = fake_controller
        runtime.runtime_state.current_device = None
        self.runtime_state_file.write_text('{"current_device": "stale-device"}', encoding="utf-8")

        with mock.patch("backend.app.runtime._get_main_module", return_value=None):
            self.assertIsNone(runtime.get_current_device())

        self.assertFalse(self.runtime_state_file.exists())



if __name__ == "__main__":
    unittest.main()