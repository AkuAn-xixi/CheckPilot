import unittest
import json
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
        self.original_platform_auth = getattr(runtime.runtime_state, "platform_auth", {})
        self.temp_dir = tempfile.TemporaryDirectory()
        self.runtime_state_file = Path(self.temp_dir.name) / "runtime_state.json"
        self.runtime_state_patch = mock.patch("backend.app.runtime.RUNTIME_STATE_FILE", self.runtime_state_file)
        self.runtime_state_patch.start()

    def tearDown(self):
        runtime.runtime_state.controller = self.original_controller
        runtime.runtime_state.current_device = self.original_current_device
        runtime.runtime_state.platform_auth = self.original_platform_auth
        self.runtime_state_patch.stop()
        self.temp_dir.cleanup()

    def test_get_current_device_does_not_probe_adb_when_state_present(self):
        """不会再因 ``adb devices`` 抖动主动清理已选设备。"""
        fake_controller = FakeController([])
        runtime.runtime_state.controller = fake_controller
        runtime.runtime_state.current_device = "device-123"

        with mock.patch("backend.app.runtime._get_main_module", return_value=None):
            self.assertEqual(runtime.get_current_device(), "device-123")

        self.assertEqual(runtime.runtime_state.current_device, "device-123")
        self.assertEqual(fake_controller.device_serial, "device-123")

    def test_prune_current_device_clears_stale_device(self):
        # 当 adb devices 返回了一台真实设备但**不包含**当前已选的，才清理。
        # 单独 [] 不算"掉线"——可能是 adb 抖动，留给用户主动刷新再判断。
        fake_controller = FakeController(["other-device"])
        runtime.runtime_state.controller = fake_controller
        runtime.runtime_state.current_device = "stale-device"
        self.runtime_state_file.write_text('{"current_device": "stale-device"}', encoding="utf-8")

        with mock.patch("backend.app.runtime._get_main_module", return_value=None):
            self.assertIsNone(runtime.prune_current_device_if_offline(["other-device"]))

        self.assertIsNone(runtime.runtime_state.current_device)
        self.assertIsNone(fake_controller.device_serial)
        self.assertFalse(self.runtime_state_file.exists())

    def test_prune_current_device_keeps_selection_when_list_empty(self):
        """adb devices 返回空（adb 抖动）时不应清理已选设备。"""
        fake_controller = FakeController([])
        runtime.runtime_state.controller = fake_controller
        runtime.runtime_state.current_device = "device-123"
        self.runtime_state_file.write_text('{"current_device": "device-123"}', encoding="utf-8")

        with mock.patch("backend.app.runtime._get_main_module", return_value=None):
            self.assertEqual(runtime.prune_current_device_if_offline([]), "device-123")

        self.assertEqual(runtime.runtime_state.current_device, "device-123")
        self.assertTrue(self.runtime_state_file.exists())

    def test_prune_current_device_keeps_active_device(self):
        fake_controller = FakeController(["device-123"])
        runtime.runtime_state.controller = fake_controller
        runtime.runtime_state.current_device = "device-123"

        with mock.patch("backend.app.runtime._get_main_module", return_value=None):
            self.assertEqual(runtime.prune_current_device_if_offline(["device-123"]), "device-123")

        self.assertEqual(fake_controller.device_serial, "device-123")
        persisted = json.loads(self.runtime_state_file.read_text(encoding="utf-8"))
        self.assertEqual(persisted["current_device"], "device-123")

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

    def test_get_current_device_returns_persisted_value_without_probing_adb(self):
        """``adb devices`` 返回空时也不会触发持久化文件被擦掉。"""
        fake_controller = FakeController([])
        runtime.runtime_state.controller = fake_controller
        runtime.runtime_state.current_device = None
        self.runtime_state_file.write_text('{"current_device": "stale-device"}', encoding="utf-8")

        with mock.patch("backend.app.runtime._get_main_module", return_value=None):
            self.assertEqual(runtime.get_current_device(), "stale-device")

        self.assertTrue(self.runtime_state_file.exists())

    def test_set_platform_auth_persists_token_for_future_reuse(self):
        runtime.runtime_state.platform_auth = {}

        runtime.set_platform_auth({
            "username": "Zephyr",
            "token": "saved-token-123",
        })

        self.assertEqual(runtime.get_platform_auth(), {
            "username": "Zephyr",
            "token": "saved-token-123",
        })
        persisted = json.loads(self.runtime_state_file.read_text(encoding="utf-8"))
        self.assertEqual(persisted["platform_auth"], {
            "username": "Zephyr",
            "token": "saved-token-123",
        })



if __name__ == "__main__":
    unittest.main()