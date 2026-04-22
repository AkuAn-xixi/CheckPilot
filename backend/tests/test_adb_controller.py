import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from backend.app.config import settings
from backend.app.utils.adb_controller import ADBController


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"test-payload"


class TakeScreenshotTests(unittest.TestCase):
    def setUp(self):
        self.controller = ADBController()
        self.controller.select_device("device-123")

    @mock.patch("backend.app.utils.adb_controller.time.sleep", return_value=None)
    def test_take_screenshot_prefers_exec_out(self, _sleep):
        with tempfile.TemporaryDirectory() as tmp_dir, mock.patch.object(settings, "SCREENSHOT_DIR", Path(tmp_dir)):
            calls = []

            def fake_run(command, check=False, stdout=None, stderr=None, **kwargs):
                calls.append(command)
                if command[:4] == ["adb", "-s", "device-123", "exec-out"]:
                    stdout.write(PNG_BYTES)
                    stdout.flush()
                    return subprocess.CompletedProcess(command, 0)
                raise AssertionError(f"unexpected adb call: {command}")

            with mock.patch("backend.app.utils.adb_controller.subprocess.run", side_effect=fake_run):
                screenshot_path = self.controller.take_screenshot("Case:1")

        self.assertIsNotNone(screenshot_path)
        self.assertEqual(Path(screenshot_path).name, "Case_1.png")
        self.assertEqual(calls, [["adb", "-s", "device-123", "exec-out", "screencap", "-p"]])

    @mock.patch("backend.app.utils.adb_controller.time.sleep", return_value=None)
    def test_take_screenshot_retries_pull_after_exec_out_failure(self, _sleep):
        with tempfile.TemporaryDirectory() as tmp_dir, mock.patch.object(settings, "SCREENSHOT_DIR", Path(tmp_dir)):
            pull_attempts = 0

            def fake_run(command, check=False, stdout=None, stderr=None, **kwargs):
                nonlocal pull_attempts

                if command[:4] == ["adb", "-s", "device-123", "exec-out"]:
                    raise subprocess.CalledProcessError(1, command)

                if command[:5] == ["adb", "-s", "device-123", "shell", "screencap"]:
                    return subprocess.CompletedProcess(command, 0)

                if command[:4] == ["adb", "-s", "device-123", "pull"]:
                    pull_attempts += 1
                    if pull_attempts == 1:
                        raise subprocess.CalledProcessError(1, command)
                    Path(command[-1]).write_bytes(PNG_BYTES)
                    return subprocess.CompletedProcess(command, 0)

                if command[:5] == ["adb", "-s", "device-123", "shell", "rm"]:
                    return subprocess.CompletedProcess(command, 0)

                raise AssertionError(f"unexpected adb call: {command}")

            with mock.patch("backend.app.utils.adb_controller.subprocess.run", side_effect=fake_run):
                screenshot_path = self.controller.take_screenshot("Retry Case")

        self.assertIsNotNone(screenshot_path)
        self.assertEqual(Path(screenshot_path).name, "Retry Case.png")
        self.assertEqual(pull_attempts, 2)


class ReadExcelCommandsTests(unittest.TestCase):
    def setUp(self):
        self.controller = ADBController()

    @mock.patch("backend.app.utils.adb_controller.pd.read_excel")
    def test_read_excel_commands_ignores_nan_placeholder_commands(self, mock_read_excel):
        mock_read_excel.return_value = pd.DataFrame([
            {
                "runOption": "Y",
                "oriStep": float("nan"),
                "preScript": "HOME/1/0, OK/1/0",
                "testID": "TC-001",
                "checkPic": float("nan"),
            }
        ])

        result = self.controller.read_excel_commands("dummy.xlsx", target_row=1)

        self.assertEqual(result["commands"], ["HOME/1/0", "OK/1/0"])
        self.assertEqual(result["valid_rows"][0]["oriStep"], "")
        self.assertEqual(result["valid_rows"][0]["preScript"], "HOME/1/0, OK/1/0")


if __name__ == "__main__":
    unittest.main()