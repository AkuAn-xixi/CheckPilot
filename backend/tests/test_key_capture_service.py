"""``key_capture_service`` 的会话逻辑用例。

用替身把 adb 隔离掉，直接驱动 ``_prime_baseline`` / ``_poll_once`` /
``_consume_getevent_stream``，避免线程与时序带来的不确定性。
"""

import threading
import unittest

from backend.app.services.key_capture_service import (
    KeyCaptureError,
    KeyCaptureService,
    extract_getevent_device_path,
    parse_getevent_line,
    resolve_script_keyname,
)

_DEVICES_BLOCK = """Event Hub State:
  BuiltInKeyboardId: -2
  Devices:
    3: input_ethrcu
      Classes: KEYBOARD | DPAD
      Path: /dev/input/event8
      Enabled: true
    13: TV BLE Remote Keyboard
      Classes: KEYBOARD | DPAD | EXTERNAL
      Path: /dev/input/event12
      Enabled: true
  Unattached video devices:
    0: <none>
"""


def _key_event(device_id, event_time, action, name, code, scan, source="KEYBOARD | DPAD", repeat_count=0):
    return (
        f"KeyEvent(deviceId={device_id}, eventTime={event_time}, source={source}, "
        f"displayId=-1, action={action}, flags=0x00000008, keyCode={name}({code}), "
        f"scanCode={scan}, metaState=0x00000000, repeatCount={repeat_count}), "
        f"policyFlags=0x67000000, age=1ms"
    )


def _dump(*events):
    """用给定事件拼一份最小可用的 dumpsys input 输出。"""
    body = "\n".join(f"    {event}" for event in events)
    return (
        _DEVICES_BLOCK
        + f"  RecentQueue: length={len(events)}\n{body}\n  PendingEvent: <none>\n"
    )


# 真机 Input Reader State 片段：Device 12 把 Event Hub 的 12、13 两个节点合并成一个
# （同一个 BLE HID 设备的键盘与多媒体键两个 application collection）。
# 注意 Reader 的编号与 Event Hub 的编号**不是同一套**。
_READER_BLOCK = """Input Reader State (Nums of device: 2):
  Device 12: TV BLE Remote Consumer Control
    EventHub Devices: [ 12 13 ]
    Generation: 77
    Sources: KEYBOARD | DPAD | JOYSTICK
  Device 9: input_ethrcu
    EventHub Devices: [ 3 ]
    Generation: 12
    Sources: KEYBOARD | DPAD
Input Processor State:
"""

# 与上面配合的 Event Hub 片段：12 与 13 分属两个节点
_MERGED_EVENT_HUB_BLOCK = """Event Hub State:
  Devices:
    3: input_ethrcu
      Path: /dev/input/event8
    12: TV BLE Remote Consumer Control
      Path: /dev/input/event11
    13: TV BLE Remote Keyboard
      Path: /dev/input/event12
  Unattached video devices:
    0: <none>
"""


def _merged_dump(*events):
    """拼一份带 Input Reader State 的 dump，模拟 BLE 遥控器双节点合并。"""
    body = "\n".join(f"    {event}" for event in events)
    return (
        _MERGED_EVENT_HUB_BLOCK
        + _READER_BLOCK
        + f"  RecentQueue: length={len(events)}\n{body}\n  PendingEvent: <none>\n"
    )


class _FakeAdb:
    """按顺序吐出预置 dump 的 ADBController 替身。"""

    def __init__(self, dumps=(), spawn_error=None):
        self._dumps = list(dumps)
        self._spawn_error = spawn_error
        self.dump_calls = 0

    def run_shell_command(self, *_args, timeout=None):
        self.dump_calls += 1
        if not self._dumps:
            raise AssertionError("用例预置的 dump 已用完")
        return self._dumps.pop(0)

    def spawn_shell_stream(self, *_args):
        if self._spawn_error is not None:
            raise self._spawn_error
        raise AssertionError("本用例不应启用伴读")


class _FakeProcess:
    """把预置行当成 getevent 的流式输出。"""

    def __init__(self, lines):
        self.stdout = list(lines)


def _feed_getevent(service, *lines):
    """把若干行 getevent 输出灌进伴读缓冲。"""
    service._consume_getevent_stream(_FakeProcess(lines))


class GeteventLineParserTests(unittest.TestCase):
    def test_parse_down_event_returns_key_name(self):
        name, pending = parse_getevent_line(
            "[   123.456789] /dev/input/event12: EV_KEY       KEY_TAB              DOWN", None
        )
        self.assertEqual(name, "TAB")
        self.assertIsNone(pending)

    def test_parse_up_event_returns_nothing(self):
        name, pending = parse_getevent_line(
            "[   123.456789] /dev/input/event12: EV_KEY       KEY_TAB              UP", "000c0085"
        )
        # 松开事件不产出键名，但仍要消费掉缓存的 MSC_SCAN
        self.assertIsNone(name)
        self.assertIsNone(pending)

    def test_parse_unknown_key_falls_back_to_scan(self):
        name, pending = parse_getevent_line(
            "[   123.456789] /dev/input/event12: EV_MSC       MSC_SCAN             000c0085", None
        )
        self.assertIsNone(name)
        self.assertEqual(pending, "000c0085")

        name, pending = parse_getevent_line(
            "[   123.456790] /dev/input/event12: EV_KEY       KEY_UNKNOWN          DOWN", pending
        )
        self.assertEqual(name, "SCAN_C0085")

    def test_parse_ignores_unrelated_lines(self):
        name, pending = parse_getevent_line('add device 1: /dev/input/event13', "000c0085")
        self.assertIsNone(name)
        self.assertEqual(pending, "000c0085")

    def test_extract_device_path_from_prefix(self):
        self.assertEqual(
            extract_getevent_device_path("[   1.2] /dev/input/event8: EV_KEY KEY_HOME DOWN"),
            "/dev/input/event8",
        )
        self.assertEqual(extract_getevent_device_path("add device 1: /dev/input/event13"), "")


class ResolveScriptKeynameTests(unittest.TestCase):
    def test_known_alias_is_applied(self):
        self.assertEqual(resolve_script_keyname("SETTINGS", 176), "SETTING")
        self.assertEqual(resolve_script_keyname("DPAD_CENTER", 23), "OK")
        self.assertEqual(resolve_script_keyname("TV_INPUT", 178), "SOURCE")

    def test_digit_key_becomes_digital(self):
        self.assertEqual(resolve_script_keyname("6", 13), "DIGITAL6")

    def test_unknown_name_is_kept_as_is(self):
        self.assertEqual(resolve_script_keyname("HK41", 261), "HK41")

    def test_anonymous_key_gets_synthetic_name(self):
        self.assertEqual(resolve_script_keyname("", 261), "KEYCODE_261")


class CaptureSessionTests(unittest.TestCase):
    def _service_with(self, dumps, spawn_error=None):
        return KeyCaptureService(_FakeAdb(dumps, spawn_error=spawn_error))

    def test_baseline_prevents_reporting_stale_events(self):
        home = _key_event(3, 1000, "DOWN", "HOME", 3, 102)
        settings = _key_event(3, 2000, "DOWN", "SETTINGS", 176, 141)

        service = self._service_with([_dump(home), _dump(home, settings)])
        service._prime_baseline()
        service._poll_once()

        events = service.list_events()["events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["android_keyname"], "SETTINGS")

    def test_injected_events_are_ignored(self):
        down = _key_event(-1, 5000, "DOWN", "UNKNOWN", 0, 0, source="UNKNOWN")
        up = _key_event(-1, 5000, "UP", "UNKNOWN", 0, 0, source="UNKNOWN")

        service = self._service_with([_dump(), _dump(down, up)])
        service._prime_baseline()
        service._poll_once()

        self.assertEqual(service.list_events()["events"], [])

    def test_key_up_is_not_captured(self):
        down = _key_event(3, 1000, "DOWN", "HOME", 3, 102)
        up = _key_event(3, 1001, "UP", "HOME", 3, 102)

        service = self._service_with([_dump(), _dump(down, up)])
        service._prime_baseline()
        service._poll_once()

        self.assertEqual(len(service.list_events()["events"]), 1)

    def test_captured_event_carries_source_device_and_alias(self):
        settings = _key_event(3, 1000, "DOWN", "SETTINGS", 176, 141)

        service = self._service_with([_dump(), _dump(settings)])
        service._prime_baseline()
        service._poll_once()

        event = service.list_events()["events"][0]
        self.assertEqual(event["device_name"], "input_ethrcu")
        self.assertEqual(event["device_path"], "/dev/input/event8")
        self.assertEqual(event["script_keyname"], "SETTING")
        self.assertEqual(event["linux_scan_code"], 141)
        self.assertTrue(event["has_usable_keycode"])

    def test_unknown_keycode_is_flagged_as_unusable(self):
        unknown = _key_event(13, 1000, "DOWN", "UNKNOWN", 0, 453)

        service = self._service_with([_dump(), _dump(unknown)])
        service._prime_baseline()
        service._poll_once()

        event = service.list_events()["events"][0]
        self.assertFalse(event["has_usable_keycode"])
        self.assertEqual(event["linux_scan_code"], 453)

    def test_paired_getevent_name_becomes_monitor_source_key(self):
        service = self._service_with([_dump(), _dump(_key_event(13, 1000, "DOWN", "TAB", 61, 15))])
        _feed_getevent(service, "[   1.1] /dev/input/event12: EV_KEY       KEY_TAB              DOWN")

        service._prime_baseline()
        service._poll_once()

        event = service.list_events()["events"][0]
        self.assertTrue(event["is_paired"])
        self.assertEqual(event["monitor_source_key"], "TAB")

    def test_merged_reader_device_pairs_across_its_nodes(self):
        # 真机实测：BLE 遥控器的键盘(EventHub 13/event12)与多媒体键(EventHub 12/event11)
        # 被合并成同一个 Reader 设备 12。按键从哪个节点来是未知的，
        # 必须把两个候选节点都拿去找，否则永远配不上对。
        service = KeyCaptureService(_FakeAdb([_merged_dump(), _merged_dump(
            _key_event(12, 1000, "DOWN", "HOME", 3, 102))]))
        _feed_getevent(service, "[   1.1] /dev/input/event12: EV_KEY       KEY_HOME             DOWN")

        service._prime_baseline()
        service._poll_once()

        event = service.list_events()["events"][0]
        self.assertEqual(event["device_name"], "TV BLE Remote Consumer Control")
        self.assertTrue(event["is_paired"])
        self.assertEqual(event["monitor_source_key"], "HOME")
        self.assertEqual(event["device_path"], "/dev/input/event12")

    def test_merged_reader_device_leaves_path_empty_when_unpaired(self):
        # 两个候选节点都拿不到键名时，来源节点确实无法确定，不能瞎填
        service = KeyCaptureService(_FakeAdb([_merged_dump(), _merged_dump(
            _key_event(12, 1000, "DOWN", "HOME", 3, 102))]))

        service._prime_baseline()
        service._poll_once()

        event = service.list_events()["events"][0]
        self.assertFalse(event["is_paired"])
        self.assertEqual(event["device_path"], "")

    def test_reader_device_id_is_not_the_event_hub_id(self):
        # Reader 的 9 号是 input_ethrcu，而 Event Hub 的 9 号并不存在；
        # 用错编号会既查不到路径、也认错设备名
        service = KeyCaptureService(_FakeAdb([_merged_dump(), _merged_dump(
            _key_event(9, 1000, "DOWN", "SETTINGS", 176, 141))]))
        _feed_getevent(service, "[   1.1] /dev/input/event8: EV_KEY       KEY_SETUP            DOWN")

        service._prime_baseline()
        service._poll_once()

        event = service.list_events()["events"][0]
        self.assertEqual(event["device_name"], "input_ethrcu")
        self.assertEqual(event["device_path"], "/dev/input/event8")
        self.assertTrue(event["is_paired"])

    def test_ambiguous_presses_leave_pairing_empty(self):
        # 同一拍里两个**不同**的键都落到同一设备：无法判断谁对应谁，宁可不猜
        service = self._service_with([_dump(), _dump(_key_event(13, 1000, "DOWN", "TAB", 61, 15))])
        _feed_getevent(
            service,
            "[   1.1] /dev/input/event12: EV_KEY       KEY_TAB              DOWN",
            "[   1.2] /dev/input/event12: EV_KEY       KEY_ESCAPE           DOWN",
        )

        service._prime_baseline()
        service._poll_once()

        event = service.list_events()["events"][0]
        self.assertFalse(event["is_paired"])
        self.assertIsNone(event["monitor_source_key"])

    def test_held_key_reports_a_single_raw_name(self):
        # 长按时 getevent 每 ~50ms 重复报一条同名 DOWN，只该记一条，否则会被误判成歧义
        service = self._service_with([_dump(), _dump(_key_event(13, 1000, "DOWN", "TAB", 61, 15))])
        _feed_getevent(
            service,
            "[   1.1] /dev/input/event12: EV_KEY       KEY_TAB              DOWN",
            "[   1.2] /dev/input/event12: EV_KEY       KEY_TAB              DOWN",
            "[   1.3] /dev/input/event12: EV_KEY       KEY_TAB              DOWN",
        )

        service._prime_baseline()
        service._poll_once()

        event = service.list_events()["events"][0]
        self.assertTrue(event["is_paired"])
        self.assertEqual(event["monitor_source_key"], "TAB")

    def test_release_resets_hold_state(self):
        # 抬起之后同一个键再按一次，应当重新算作一次新的按下
        service = self._service_with([_dump(), _dump(_key_event(13, 1000, "DOWN", "TAB", 61, 15))])
        _feed_getevent(
            service,
            "[   1.1] /dev/input/event12: EV_KEY       KEY_TAB              DOWN",
            "[   1.2] /dev/input/event12: EV_KEY       KEY_TAB              UP",
            "[   1.3] /dev/input/event12: EV_KEY       KEY_TAB              DOWN",
        )

        with service._raw_lock:
            self.assertEqual(list(service._raw_names["/dev/input/event12"]), ["TAB", "TAB"])

    def test_held_key_yields_a_single_capture(self):
        # 真机上按住不放会让内核每 ~50ms 补一条 DOWN，每条 eventTime 都不同
        held = [
            _key_event(12, 1000, "DOWN", "HOME", 3, 102, repeat_count=0),
            _key_event(12, 1050, "DOWN", "HOME", 3, 102, repeat_count=1),
            _key_event(12, 1100, "DOWN", "HOME", 3, 102, repeat_count=2),
        ]

        service = self._service_with([_dump(), _dump(*held)])
        service._prime_baseline()
        service._poll_once()

        events = service.list_events()["events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["android_keyname"], "HOME")

    def test_list_events_returns_only_entries_after_since_seq(self):
        first = _key_event(3, 1000, "DOWN", "HOME", 3, 102)
        second = _key_event(3, 2000, "DOWN", "BACK", 4, 158)

        service = self._service_with([_dump(), _dump(first, second)])
        service._prime_baseline()
        service._poll_once()

        self.assertEqual(len(service.list_events()["events"]), 2)
        later = service.list_events(since_seq=1)["events"]
        self.assertEqual([item["android_keyname"] for item in later], ["BACK"])
        self.assertEqual(later[-1]["seq"], 2)


class DegradedModeTests(unittest.TestCase):
    def test_missing_companion_keeps_session_usable(self):
        service = KeyCaptureService(
            _FakeAdb(
                [_dump(), _dump(_key_event(3, 1000, "DOWN", "HOME", 3, 102))],
                spawn_error=RuntimeError("getevent 不可用"),
            )
        )
        service._prime_baseline()

        # 伴读线程入口直接跑一遍：应当只记录错误，不抛出
        service._run_companion()
        self.assertIn("getevent 伴读不可用", service.status()["last_error"])

        service._poll_once()
        event = service.list_events()["events"][0]
        self.assertEqual(event["android_keyname"], "HOME")
        self.assertFalse(event["is_paired"])


class _FlakyAdb:
    """先连续失败若干次，随后按顺序吐 dump，吐完继续失败。

    用来复现真机上的 adb 抖动（USB 重枚举、ADB server 忙）。
    """

    def __init__(self, failures, dumps):
        self._remaining_failures = failures
        self._dumps = list(dumps)
        self.read_count = 0

    def run_shell_command(self, *_args, timeout=None):
        self.read_count += 1
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise RuntimeError("adb.exe: no devices/emulators found")
        if not self._dumps:
            raise RuntimeError("adb.exe: no devices/emulators found")
        return self._dumps.pop(0)

    def spawn_shell_stream(self, *_args):
        raise RuntimeError("本用例不启用伴读")


class RetryTests(unittest.TestCase):
    """单拍内的快速重试：一次抖动不该丢掉这一拍的按键。"""

    def test_poll_retries_within_one_tick(self):
        adb = _FlakyAdb(2, [_dump(_key_event(3, 1000, "DOWN", "HOME", 3, 102))])

        service = KeyCaptureService(adb)
        service._poll_once()

        self.assertEqual(adb.read_count, 3, "应重试到第 3 次才成功")
        self.assertEqual(service.list_events()["events"][0]["android_keyname"], "HOME")

    def test_poll_gives_up_after_all_attempts(self):
        adb = _FlakyAdb(99, [])

        service = KeyCaptureService(adb)
        with self.assertRaises(KeyCaptureError):
            service._poll_once()

        self.assertEqual(adb.read_count, 3, "重试用尽后应抛出，交给外层的连续失败计数")

    def test_baseline_also_retries(self):
        adb = _FlakyAdb(1, [_dump(_key_event(3, 1000, "DOWN", "HOME", 3, 102))])

        service = KeyCaptureService(adb)
        service._prime_baseline()

        # 陈旧事件只该被记为「已见过」，不该产出捕获结果
        self.assertEqual(service.list_events()["events"], [])


class PollerToleranceTests(unittest.TestCase):
    """轮询线程对单次 adb 失败的容忍度。"""

    @staticmethod
    def _run_poller(service):
        """在独立线程里跑轮询入口，返回时线程必定已退出。"""
        service._is_running = True
        worker = threading.Thread(target=service._run_poller, daemon=True)
        worker.start()
        worker.join(timeout=5)
        assert not worker.is_alive(), "轮询线程未按预期退出"

    def test_transient_failure_keeps_capturing(self):
        adb = _FlakyAdb(2, [_dump(), _dump(_key_event(3, 1000, "DOWN", "HOME", 3, 102))])
        service = KeyCaptureService(adb, poll_interval=0.01)

        self._run_poller(service)

        # 头两次失败若直接收工，就轮不到后面的 dump，这里也不可能拿到 HOME
        names = [event["android_keyname"] for event in service.list_events()["events"]]
        self.assertEqual(names, ["HOME"])

    def test_persistent_failure_ends_session(self):
        service = KeyCaptureService(_FlakyAdb(0, [_dump()]), poll_interval=0.01)

        self._run_poller(service)

        status = service.status()
        self.assertFalse(status["is_running"])
        self.assertIn("no devices", status["last_error"])

    def test_status_reports_known_sources(self):
        service = KeyCaptureService(_FakeAdb([_dump()]))
        service._prime_baseline()

        sources = {item["device_id"]: item for item in service.status()["sources"]}
        self.assertEqual(sources[3]["name"], "input_ethrcu")
        self.assertEqual(sources[13]["paths"], ["/dev/input/event12"])

    def test_stop_is_idempotent_when_not_running(self):
        service = KeyCaptureService(_FakeAdb([]))
        service.stop()  # 不应抛出
        self.assertFalse(service.status()["is_running"])

    def test_start_twice_raises(self):
        service = KeyCaptureService(_FakeAdb([]))
        service._is_running = True
        with self.assertRaises(KeyCaptureError):
            service.start()


if __name__ == "__main__":
    unittest.main()
