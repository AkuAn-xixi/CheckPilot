import json
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from backend.app.config import settings
from backend.app.utils.adb_controller import (
    ADBController,
    SENDEVENT_LONG_PRESS_DEFAULT_TIMEOUT_US,
    SENDEVENT_LONG_PRESS_MARGIN_US,
    _parse_repeat_count,
    _strip_adb_prefix_tokens,
    get_custom_commands,
    is_valid_repeat_spec,
)


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

    @mock.patch("backend.app.utils.adb_controller.pd.read_excel")
    def test_read_excel_commands_cache_hit_slices_target_row(self, mock_read_excel):
        # 首次调用（无 target_row，相当于前端“分析”步骤）填充缓存
        mock_read_excel.return_value = pd.DataFrame([
            {"runOption": "Y", "oriStep": "POWER/1/0", "preScript": "", "testID": "TC-001"},
            {"runOption": "Y", "oriStep": "OK(250000)/1/100", "preScript": "", "testID": "TC-002"},
        ])
        self.controller.read_excel_commands("dummy.xlsx")

        # 第二次调用命中缓存，target_row 是 valid_rows 的 1 基索引（长按命令所在行）
        result = self.controller.read_excel_commands("dummy.xlsx", target_row=2)

        self.assertEqual(result["commands"], ["OK(250000)/1/100"])
        self.assertEqual(len(result["valid_rows"]), 2)


class ParseRepeatCountTests(unittest.TestCase):
    @mock.patch("backend.app.utils.adb_controller.random.randint")
    def test_fixed_numeric_repeat_keeps_existing_semantics(self, mock_randint):
        self.assertEqual(_parse_repeat_count("3", "0"), 3)
        self.assertEqual(_parse_repeat_count("0", "0"), 0)
        mock_randint.assert_not_called()

    @mock.patch("backend.app.utils.adb_controller.random.randint")
    def test_x_with_explicit_upper(self, mock_randint):
        mock_randint.return_value = 4
        self.assertEqual(_parse_repeat_count("X:10", "0"), 4)
        mock_randint.assert_called_once_with(1, 10)

    @mock.patch("backend.app.utils.adb_controller.random.randint")
    def test_lowercase_x_with_explicit_upper(self, mock_randint):
        mock_randint.return_value = 2
        self.assertEqual(_parse_repeat_count("x:8", "0"), 2)
        mock_randint.assert_called_once_with(1, 8)

    @mock.patch("backend.app.utils.adb_controller.random.randint")
    def test_x_defaults_to_wait_time_upper(self, mock_randint):
        mock_randint.return_value = 3
        self.assertEqual(_parse_repeat_count("X", "5"), 3)
        mock_randint.assert_called_once_with(1, 5)

    @mock.patch("backend.app.utils.adb_controller.random.randint")
    def test_x_upper_truncates_fractional_wait_time(self, mock_randint):
        mock_randint.return_value = 1
        self.assertEqual(_parse_repeat_count("X", "2.5"), 1)
        mock_randint.assert_called_once_with(1, 2)

    @mock.patch("backend.app.utils.adb_controller.random.randint")
    def test_x_upper_clamps_to_one_for_zero_wait_time(self, mock_randint):
        mock_randint.return_value = 1
        self.assertEqual(_parse_repeat_count("X", "0"), 1)
        mock_randint.assert_called_once_with(1, 1)

    @mock.patch("backend.app.utils.adb_controller.random.randint")
    def test_x_range_with_lower_and_upper(self, mock_randint):
        mock_randint.return_value = 3
        self.assertEqual(_parse_repeat_count("X:(2:5)", "0"), 3)
        mock_randint.assert_called_once_with(2, 5)

    def test_x_zero_zero_range_returns_zero_without_random(self):
        with mock.patch("backend.app.utils.adb_controller.random.randint") as mock_randint:
            self.assertEqual(_parse_repeat_count("X:(0:0)", "0"), 0)
        mock_randint.assert_not_called()

    @mock.patch("backend.app.utils.adb_controller.random.randint")
    def test_x_range_can_resolve_to_zero(self, mock_randint):
        mock_randint.return_value = 0
        self.assertEqual(_parse_repeat_count("X:(0:3)", "0"), 0)
        mock_randint.assert_called_once_with(0, 3)

    def test_invalid_repeat_token_raises(self):
        for token in ("abc", "X:", "X:-1", "X:1.5", "1.5", "X:(5:2)", ""):
            with self.assertRaises(ValueError, msg=token):
                _parse_repeat_count(token, "1")

    def test_invalid_wait_time_raises(self):
        with self.assertRaises(ValueError):
            _parse_repeat_count("X", "abc")


class IsValidRepeatSpecTests(unittest.TestCase):
    def test_accepts_positive_integers(self):
        self.assertTrue(is_valid_repeat_spec("3"))
        self.assertTrue(is_valid_repeat_spec("1"))

    def test_accepts_x_without_upper(self):
        self.assertTrue(is_valid_repeat_spec("X"))
        self.assertTrue(is_valid_repeat_spec("x"))

    def test_accepts_x_with_positive_upper(self):
        self.assertTrue(is_valid_repeat_spec("X:5"))
        self.assertTrue(is_valid_repeat_spec("x:1"))

    def test_accepts_x_range_syntax(self):
        self.assertTrue(is_valid_repeat_spec("X:(0:0)"))
        self.assertTrue(is_valid_repeat_spec("X:(0:5)"))
        self.assertTrue(is_valid_repeat_spec("x:(2:8)"))

    def test_rejects_invalid_specs(self):
        for token in ("0", "-1", "X:0", "X:", "X:-1", "X:1.5", "X:(5:2)", "X:(a:b)", "X:()", "X:(0:0:0)", "abc", "", " "):
            self.assertFalse(is_valid_repeat_spec(token), msg=token)


class ExecuteCommandsRandomRepeatTests(unittest.TestCase):
    @mock.patch("backend.app.utils.adb_controller.random.randint", return_value=3)
    @mock.patch("backend.app.utils.adb_controller.subprocess.run")
    def test_execute_commands_resolves_x_repeat(self, mock_run, mock_randint):
        controller = ADBController()
        controller.select_device("device-123")
        mock_run.return_value = subprocess.CompletedProcess(["adb"], 0, stdout="", stderr="")

        results = controller.execute_commands("OK/X:5/0")

        self.assertEqual(len(results), 3)
        self.assertTrue(all(r["status"] == "success" for r in results))
        mock_randint.assert_called_once_with(1, 5)

    @mock.patch("backend.app.utils.adb_controller.random.randint", return_value=0)
    @mock.patch("backend.app.utils.adb_controller.subprocess.run")
    def test_execute_commands_skips_when_random_zero(self, mock_run, mock_randint):
        controller = ADBController()
        controller.select_device("device-123")

        results = controller.execute_commands("OK/X:(0:5)/0")

        self.assertEqual(results, [{"status": "info", "message": "已跳过 OK（随机次数为 0）"}])
        mock_randint.assert_called_once_with(0, 5)
        mock_run.assert_not_called()

    @mock.patch("backend.app.utils.adb_controller.subprocess.run")
    def test_execute_commands_skips_zero_zero_range(self, mock_run):
        controller = ADBController()
        controller.select_device("device-123")

        results = controller.execute_commands("OK/X:(0:0)/0")

        self.assertEqual(results, [{"status": "info", "message": "已跳过 OK（随机次数为 0）"}])
        mock_run.assert_not_called()


class ReadExcelCommandsRandomRepeatTests(unittest.TestCase):
    def setUp(self):
        self.controller = ADBController()

    @mock.patch("backend.app.utils.adb_controller.pd.read_excel")
    def test_read_excel_commands_accepts_random_repeat(self, mock_read_excel):
        mock_read_excel.return_value = pd.DataFrame([
            {"runOption": "Y", "oriStep": "OK/X:5/1", "preScript": "", "testID": "TC-X"}
        ])

        result = self.controller.read_excel_commands("dummy.xlsx")

        self.assertEqual(len(result["valid_rows"]), 1)
        self.assertEqual(result["valid_rows"][0]["commands"], ["OK/X:5/1"])

    @mock.patch("backend.app.utils.adb_controller.pd.read_excel")
    def test_read_excel_commands_accepts_not_assert(self, mock_read_excel):
        mock_read_excel.return_value = pd.DataFrame([
            {"runOption": "Y", "oriStep": "NOTASSERT/1/1", "preScript": "", "testID": "TC-NA"}
        ])

        result = self.controller.read_excel_commands("dummy.xlsx")

        self.assertEqual(len(result["valid_rows"]), 1)
        self.assertEqual(result["valid_rows"][0]["commands"], ["NOTASSERT/1/1"])

    @mock.patch("backend.app.utils.adb_controller.pd.read_excel")
    def test_read_excel_commands_accepts_zero_zero_range(self, mock_read_excel):
        mock_read_excel.return_value = pd.DataFrame([
            {"runOption": "Y", "oriStep": "OK/X:(0:0)/1", "preScript": "", "testID": "TC-X0"}
        ])

        result = self.controller.read_excel_commands("dummy.xlsx")

        self.assertEqual(len(result["valid_rows"]), 1)
        self.assertEqual(result["valid_rows"][0]["commands"], ["OK/X:(0:0)/1"])

    @mock.patch("backend.app.utils.adb_controller.pd.read_excel")
    def test_read_excel_commands_rejects_invalid_repeat(self, mock_read_excel):
        mock_read_excel.return_value = pd.DataFrame([
            {"runOption": "Y", "oriStep": "OK/abc/1", "preScript": "", "testID": "TC-X"}
        ])

        result = self.controller.read_excel_commands("dummy.xlsx")

        self.assertEqual(len(result["valid_rows"]), 0)
        self.assertIn("无法解析", result["skipped_rows"][0]["reason"])


class StripAdbPrefixTests(unittest.TestCase):
    def test_strips_leading_adb(self):
        self.assertEqual(
            _strip_adb_prefix_tokens("adb shell am force-stop com.netflix.ninja"),
            ["shell", "am", "force-stop", "com.netflix.ninja"],
        )

    def test_strips_adb_with_serial(self):
        self.assertEqual(
            _strip_adb_prefix_tokens("adb -s 12345 shell input keyevent 4"),
            ["shell", "input", "keyevent", "4"],
        )

    def test_keeps_non_adb_command(self):
        self.assertEqual(
            _strip_adb_prefix_tokens("shell input keyevent 4"),
            ["shell", "input", "keyevent", "4"],
        )

    def test_returns_empty_for_empty_or_unparsable(self):
        self.assertEqual(_strip_adb_prefix_tokens(""), [])
        self.assertEqual(_strip_adb_prefix_tokens("adb 'unclosed"), [])


class GetCustomCommandsTests(unittest.TestCase):
    def test_reads_active_scheme_custom_commands(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_file = Path(tmp_dir) / "customization.json"
            cfg_file.write_text(json.dumps({
                "active_scheme": "方案B",
                "schemes": {
                    "方案A": {"custom_commands": {"AAA": "adb shell echo a"}},
                    "方案B": {"custom_commands": {"CLAERNETFLIX": "adb shell am force-stop com.netflix.ninja"}},
                }
            }), encoding="utf-8")
            with mock.patch("backend.app.utils.adb_controller.settings") as mock_settings:
                mock_settings.CUSTOMIZATION_FILE = cfg_file
                self.assertEqual(
                    get_custom_commands(),
                    {"CLAERNETFLIX": "adb shell am force-stop com.netflix.ninja"},
                )

    def test_returns_empty_when_no_config(self):
        with mock.patch("backend.app.utils.adb_controller.settings") as mock_settings:
            mock_settings.CUSTOMIZATION_FILE = Path(tempfile.gettempdir()) / "definitely_missing.json"
            self.assertEqual(get_custom_commands(), {})


class RunCustomCommandTests(unittest.TestCase):
    def setUp(self):
        self.controller = ADBController()
        self.controller.select_device("device-123")

    @mock.patch("backend.app.utils.adb_controller.subprocess.run")
    def test_executes_stripped_command(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(["adb"], 0, stdout="", stderr="")

        ok = self.controller.run_custom_command("CLAERNETFLIX", "adb shell am force-stop com.netflix.ninja", 0)

        self.assertTrue(ok)
        self.assertEqual(
            mock_run.call_args[0][0],
            ["adb", "-s", "device-123", "shell", "am", "force-stop", "com.netflix.ninja"],
        )

    @mock.patch("backend.app.utils.adb_controller.time.sleep", return_value=None)
    @mock.patch("backend.app.utils.adb_controller.subprocess.run")
    def test_retries_connection_error_then_fails(self, mock_run, _sleep):
        mock_run.return_value = subprocess.CompletedProcess(["adb"], 1, stdout="", stderr="error: device not found")
        with mock.patch.object(self.controller, "_reconnect_device", return_value=True):
            ok = self.controller.run_custom_command("CLAERNETFLIX", "shell input keyevent 4")

        self.assertFalse(ok)
        self.assertEqual(mock_run.call_count, 3)  # 1 + max_retries=2

    @mock.patch("backend.app.utils.adb_controller.time.sleep", return_value=None)
    @mock.patch("backend.app.utils.adb_controller.subprocess.run")
    def test_timeout_returns_false(self, mock_run, _sleep):
        mock_run.side_effect = subprocess.TimeoutExpired(["adb"], 15)
        with mock.patch.object(self.controller, "_reconnect_device", return_value=True):
            ok = self.controller.run_custom_command("CLAERNETFLIX", "shell input keyevent 4")

        self.assertFalse(ok)
        self.assertEqual(mock_run.call_count, 3)

    @mock.patch("backend.app.utils.adb_controller.subprocess.run")
    def test_empty_command_returns_false(self, mock_run):
        ok = self.controller.run_custom_command("CLAERNETFLIX", "", 0)
        self.assertFalse(ok)
        mock_run.assert_not_called()


class ExecuteCommandsCustomCommandTests(unittest.TestCase):
    @mock.patch("backend.app.utils.adb_controller.get_custom_commands")
    @mock.patch("backend.app.utils.adb_controller.subprocess.run")
    def test_execute_commands_runs_custom_command(self, mock_run, mock_custom):
        controller = ADBController()
        controller.select_device("device-123")
        mock_custom.return_value = {"CLAERNETFLIX": "adb shell am force-stop com.netflix.ninja"}
        mock_run.return_value = subprocess.CompletedProcess(["adb"], 0, stdout="", stderr="")

        results = controller.execute_commands("CLAERNETFLIX/1/0")

        self.assertEqual(results, [{"status": "success", "message": "已执行自定义命令: CLAERNETFLIX"}])
        self.assertEqual(
            mock_run.call_args[0][0],
            ["adb", "-s", "device-123", "shell", "am", "force-stop", "com.netflix.ninja"],
        )

    @mock.patch("backend.app.utils.adb_controller.get_custom_commands")
    def test_execute_commands_unknown_key_still_errors(self, mock_custom):
        controller = ADBController()
        controller.select_device("device-123")
        mock_custom.return_value = {"CLAERNETFLIX": "adb shell am force-stop com.netflix.ninja"}

        results = controller.execute_commands("NOT_A_KEY/1/0")

        self.assertEqual(results, [{"status": "error", "message": "未知按键: NOT_A_KEY"}])


class ReadExcelCommandsCustomCommandTests(unittest.TestCase):
    def setUp(self):
        self.controller = ADBController()

    @mock.patch("backend.app.utils.adb_controller.get_custom_commands")
    @mock.patch("backend.app.utils.adb_controller.pd.read_excel")
    def test_read_excel_commands_accepts_custom_command(self, mock_read_excel, mock_custom):
        mock_custom.return_value = {"CLAERNETFLIX": "adb shell am force-stop com.netflix.ninja"}
        mock_read_excel.return_value = pd.DataFrame([
            {"runOption": "Y", "oriStep": "CLAERNETFLIX/1/1", "preScript": "", "testID": "TC-CC"}
        ])

        result = self.controller.read_excel_commands("dummy.xlsx")

        self.assertEqual(len(result["valid_rows"]), 1)
        self.assertEqual(result["valid_rows"][0]["commands"], ["CLAERNETFLIX/1/1"])


class SendeventLongPressTests(unittest.TestCase):
    def setUp(self):
        self.controller = ADBController()
        self.controller.select_device("device-123")

    def _fake_run(self, shell_calls):
        def fake_run(command, check=False, capture_output=False, text=False, timeout=None, **kwargs):
            shell_calls.append(command)
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        return fake_run

    def test_hold_below_device_timeout_is_auto_extended(self):
        shell_calls = []

        with mock.patch.object(self.controller, "_get_long_press_timeout_us", return_value=500000), \
             mock.patch.object(self.controller, "_detect_sendevent_device", return_value="/dev/input/event0"), \
             mock.patch("backend.app.utils.adb_controller.subprocess.run",
                        side_effect=self._fake_run(shell_calls)):
            ok = self.controller.send_long_press(20, "DOWN", 350000, 0)

        self.assertTrue(ok)
        self.assertEqual(len(shell_calls), 1)
        expected_hold = 500000 + SENDEVENT_LONG_PRESS_MARGIN_US
        self.assertIn(f"usleep {expected_hold}", shell_calls[0][-1])

    def test_hold_above_device_timeout_keeps_configured_value(self):
        shell_calls = []

        with mock.patch.object(self.controller, "_get_long_press_timeout_us", return_value=500000), \
             mock.patch.object(self.controller, "_detect_sendevent_device", return_value="/dev/input/event0"), \
             mock.patch("backend.app.utils.adb_controller.subprocess.run",
                        side_effect=self._fake_run(shell_calls)):
            ok = self.controller.send_long_press(20, "DOWN", 700000, 0)

        self.assertTrue(ok)
        self.assertEqual(len(shell_calls), 1)
        self.assertIn("usleep 700000", shell_calls[0][-1])

    def test_timeout_query_falls_back_when_value_invalid(self):
        def fake_run(command, capture_output=False, text=False, timeout=None, **kwargs):
            return subprocess.CompletedProcess(command, 0, stdout="null\n", stderr="")

        with mock.patch("backend.app.utils.adb_controller.subprocess.run", side_effect=fake_run):
            self.assertEqual(
                self.controller._get_long_press_timeout_us(),
                SENDEVENT_LONG_PRESS_DEFAULT_TIMEOUT_US,
            )


class SendeventLongPressFallbackTests(unittest.TestCase):
    """sendevent 长按失败时的回退链路（adb root → input keyevent --longpress）。"""

    def setUp(self):
        self.controller = ADBController()
        self.controller.select_device("device-123")
        self.patch_method = mock.patch(
            "backend.app.utils.adb_controller._get_long_press_method", return_value="auto")
        self.patch_method.start()
        self.addCleanup(self.patch_method.stop)
        self.patch_timeout = mock.patch.object(
            self.controller, "_get_long_press_timeout_us", return_value=500000)
        self.patch_timeout.start()
        self.addCleanup(self.patch_timeout.stop)
        self.patch_device = mock.patch.object(
            self.controller, "_detect_sendevent_device", return_value="/dev/input/event0")
        self.patch_device.start()
        self.addCleanup(self.patch_device.stop)

    def _is_sendevent(self, command):
        return command[:4] == ["adb", "-s", "device-123", "shell"] and str(command[4]).startswith("sendevent ")

    def _is_input_longpress(self, command):
        return command[:5] == ["adb", "-s", "device-123", "shell", "input"] \
            and command[5:7] == ["keyevent", "--longpress"]

    def test_permission_denied_falls_back_to_input_longpress(self):
        calls = []

        def fake_run(command, check=False, capture_output=False, text=False, timeout=None, **kwargs):
            calls.append(command)
            if self._is_sendevent(command):
                raise subprocess.CalledProcessError(
                    1, command, stderr="sendevent: /dev/input/event0: Permission denied")
            if command[3] == "root":  # 生产固件不支持 adb root
                return subprocess.CompletedProcess(
                    command, 0, stdout="adbd cannot run as root in production builds\n", stderr="")
            if self._is_input_longpress(command):
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            raise AssertionError(f"unexpected adb call: {command}")

        with mock.patch("backend.app.utils.adb_controller.subprocess.run", side_effect=fake_run):
            ok = self.controller.send_long_press(20, "DOWN", 500000, 0)

        self.assertTrue(ok)
        input_calls = [c for c in calls if self._is_input_longpress(c)]
        self.assertEqual(len(input_calls), 1)
        self.assertEqual(input_calls[0][-1], "20")

    def test_permission_denied_adb_root_retries_sendevent(self):
        calls = []
        sendevent_attempts = {"count": 0}

        def fake_run(command, check=False, capture_output=False, text=False, timeout=None, **kwargs):
            calls.append(command)
            if self._is_sendevent(command):
                if sendevent_attempts["count"] < 1:
                    sendevent_attempts["count"] += 1
                    raise subprocess.CalledProcessError(
                        1, command, stderr="sendevent: /dev/input/event0: Permission denied")
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            if command[3] == "root":
                return subprocess.CompletedProcess(command, 0, stdout="restarting adbd as root\n", stderr="")
            if command[3] == "get-state":
                return subprocess.CompletedProcess(command, 0, stdout="device\n", stderr="")
            raise AssertionError(f"unexpected adb call: {command}")

        with mock.patch("backend.app.utils.adb_controller.subprocess.run", side_effect=fake_run):
            ok = self.controller.send_long_press(20, "DOWN", 500000, 0)

        self.assertTrue(ok)
        root_calls = [c for c in calls if c[3] == "root"]
        input_calls = [c for c in calls if self._is_input_longpress(c)]
        self.assertEqual(len(root_calls), 1)
        self.assertEqual(sendevent_attempts["count"], 1)
        self.assertEqual(input_calls, [], "adb root 成功后不应再回退到 input --longpress")

    def test_missing_linux_keycode_falls_back_to_input_longpress(self):
        calls = []

        def fake_run(command, check=False, capture_output=False, text=False, timeout=None, **kwargs):
            calls.append(command)
            if self._is_input_longpress(command):
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            raise AssertionError(f"unexpected adb call: {command}")

        with mock.patch.object(self.controller, "_get_linux_keycode", side_effect=ValueError("no mapping")), \
             mock.patch("backend.app.utils.adb_controller.subprocess.run", side_effect=fake_run):
            ok = self.controller.send_long_press(360, "APPS", 500000, 0)

        self.assertTrue(ok)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][-1], "360")

    def test_forced_input_method_skips_sendevent(self):
        calls = []

        def fake_run(command, check=False, capture_output=False, text=False, timeout=None, **kwargs):
            calls.append(command)
            if self._is_input_longpress(command):
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            raise AssertionError(f"unexpected adb call: {command}")

        with mock.patch("backend.app.utils.adb_controller._get_long_press_method", return_value="input"), \
             mock.patch("backend.app.utils.adb_controller.subprocess.run", side_effect=fake_run):
            ok = self.controller.send_long_press(20, "DOWN", 500000, 0)

        self.assertTrue(ok)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][4:], ["input", "keyevent", "--longpress", "20"])

    def test_forced_sendevent_method_returns_false_on_permission_denied(self):
        calls = []

        def fake_run(command, check=False, capture_output=False, text=False, timeout=None, **kwargs):
            calls.append(command)
            if self._is_sendevent(command):
                raise subprocess.CalledProcessError(
                    1, command, stderr="sendevent: /dev/input/event0: Permission denied")
            if command[3] == "root":
                return subprocess.CompletedProcess(
                    command, 0, stdout="adbd cannot run as root in production builds\n", stderr="")
            raise AssertionError(f"unexpected adb call: {command}")

        with mock.patch("backend.app.utils.adb_controller._get_long_press_method", return_value="sendevent"), \
             mock.patch("backend.app.utils.adb_controller.subprocess.run", side_effect=fake_run):
            ok = self.controller.send_long_press(20, "DOWN", 500000, 0)

        self.assertFalse(ok)
        input_calls = [c for c in calls if self._is_input_longpress(c)]
        self.assertEqual(input_calls, [], "sendevent 模式下不应回退到 input --longpress")


class ReadLastTtsTextTests(unittest.TestCase):
    def setUp(self):
        self.controller = ADBController()
        self.controller.select_device("device-123")

    def test_get_last_tts_text_returns_last_matching_value(self):
        # 实际设备格式（无引号）
        output = "".join([
            '07-16 06:33:00.047  1945  2020 E SVOX Pico Engine: tts aric char = first text\n',
            '07-16 06:33:01.047  1945  2020 E SVOX Pico Engine: tts aric char = second text\n',
        ])

        def fake_run(command, check=False, capture_output=False, text=False, encoding=None, errors=None, **kwargs):
            self.assertEqual(command, ["adb", "-s", "device-123", "shell", "logcat -d | grep 'tts aric char'"])
            return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

        with mock.patch("backend.app.utils.adb_controller.subprocess.run", side_effect=fake_run):
            result = self.controller.get_last_tts_text()

        self.assertEqual(result, "second text")

    def test_get_last_tts_text_handles_quoted_format(self):
        # 兼容引号包裹格式
        output = '04-28 20:00:00.000 I SVOX Pico Engine: tts aric char ="quoted text"\n'

        def fake_run(command, check=False, capture_output=False, text=False, encoding=None, errors=None, **kwargs):
            return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

        with mock.patch("backend.app.utils.adb_controller.subprocess.run", side_effect=fake_run):
            result = self.controller.get_last_tts_text()

        self.assertEqual(result, "quoted text")

    def test_get_last_tts_text_returns_none_when_no_match(self):
        def fake_run(command, check=False, capture_output=False, text=False, encoding=None, errors=None, **kwargs):
            return subprocess.CompletedProcess(command, 0, stdout="no matching log\n", stderr="")

        with mock.patch("backend.app.utils.adb_controller.subprocess.run", side_effect=fake_run):
            result = self.controller.get_last_tts_text()

        self.assertIsNone(result)


class CommandExecutionStopTests(unittest.TestCase):
    def test_execute_commands_stops_during_delay(self):
        controller = ADBController()
        controller.select_device("device-123")
        results_holder = {}
        adb_calls = []

        def fake_run(command, shell=False, check=False, **kwargs):
            adb_calls.append(command)
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        def run_commands():
            results_holder["results"] = controller.execute_commands("OK/1/1,DOWN/1/0")

        with mock.patch("backend.app.utils.adb_controller.subprocess.run", side_effect=fake_run):
            worker = threading.Thread(target=run_commands)
            started = time.perf_counter()
            worker.start()
            time.sleep(0.15)
            self.assertTrue(controller.request_stop())
            worker.join(timeout=2)
            elapsed = time.perf_counter() - started

        self.assertFalse(worker.is_alive())
        self.assertLess(elapsed, 0.8)
        self.assertEqual(len(adb_calls), 1)
        self.assertEqual(
            results_holder["results"],
            [
                {"status": "success", "message": "已发送: OK"},
                {"status": "info", "message": "命令执行已停止"},
            ],
        )


if __name__ == "__main__":
    unittest.main()