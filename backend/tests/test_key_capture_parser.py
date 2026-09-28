"""``input_dump_parser`` 的解析用例。

样本取自真机（WhaleTV bs30a5x / Android 14）的 ``adb shell dumpsys input`` 输出，
保留了实测遇到的几种形态：FocusEvent 混排、注入事件（deviceId=-1）、
数字型按键名（``keyCode=6(13)``）、以及 Path 为 ``<virtual>`` 的虚拟节点。
"""

import unittest

from backend.app.utils.input_dump_parser import (
    parse_input_devices,
    parse_recent_queue,
)

# 真机 RecentQueue 片段：物理按键（deviceId=3）、FocusEvent、注入事件（deviceId=-1）各若干条。
_RECENT_QUEUE_FIXTURE = """  RecentQueue: length=10
    KeyEvent(deviceId=3, eventTime=1966521419000, source=KEYBOARD | DPAD, displayId=-1, action=DOWN, flags=0x00000008, keyCode=MENU(82), scanCode=139, metaState=0x00000000, repeatCount=0), policyFlags=0x67000000, age=598508ms
    KeyEvent(deviceId=3, eventTime=1966724025000, source=KEYBOARD | DPAD, displayId=-1, action=UP, flags=0x00000008, keyCode=MENU(82), scanCode=139, metaState=0x00000000, repeatCount=0), policyFlags=0x67000000, age=598306ms
    KeyEvent(deviceId=3, eventTime=1966944365000, source=KEYBOARD | DPAD, displayId=-1, action=DOWN, flags=0x00000008, keyCode=6(13), scanCode=7, metaState=0x00000000, repeatCount=0), policyFlags=0x67000000, age=598085ms
    FocusEvent(hasFocus=false), age=586666ms
    FocusEvent(hasFocus=true), age=586366ms
    KeyEvent(deviceId=3, eventTime=1978138906000, source=KEYBOARD | DPAD, displayId=-1, action=DOWN, flags=0x00000008, keyCode=SETTINGS(176), scanCode=141, metaState=0x00000000, repeatCount=0), policyFlags=0x67000000, age=586891ms
    KeyEvent(deviceId=-1, eventTime=2587693000000, source=UNKNOWN, displayId=-1, action=DOWN, flags=0x00000000, keyCode=UNKNOWN(0), scanCode=0, metaState=0x00000000, repeatCount=0), policyFlags=0x6b000000, age=1921ms
    KeyEvent(deviceId=-1, eventTime=2587693000000, source=UNKNOWN, displayId=-1, action=UP, flags=0x00000000, keyCode=UNKNOWN(0), scanCode=0, metaState=0x00000000, repeatCount=0), policyFlags=0x6b000000, age=1921ms
  PendingEvent: <none>
"""

# 真机 Event Hub State 片段：含带 Path 的实体设备、Path 为 <virtual> 的虚拟节点、
# 以及紧随其后的同级区块（用于验证扫描会正确收尾）。
_DEVICES_FIXTURE = """Event Hub State:
  BuiltInKeyboardId: -2
  Devices:
    13: TV BLE Remote Keyboard
      Classes: KEYBOARD | DPAD | EXTERNAL
      Path: /dev/input/event12
      Enabled: true
      Identifier: bus=0x0005, vendor=0x1d5a, product=0xc080, version=0x0111
    3: input_ethrcu
      Classes: KEYBOARD | DPAD
      Path: /dev/input/event8
      Enabled: true
    9: ir_keypad0_1
      Classes: KEYBOARD | DPAD
      Path: <virtual>
      Enabled: true
    1: AML-AUGESOUND Headphones
      Classes: SWITCH
      Path: /dev/input/event10
      Enabled: true
  Unattached video devices:
    0: <none>
      Classes: VIDEO
"""


class RecentQueueParserTests(unittest.TestCase):
    def setUp(self):
        self.records = parse_recent_queue(_RECENT_QUEUE_FIXTURE)

    def test_parse_skips_focus_events(self):
        # 8 行里有 6 条 KeyEvent、2 条 FocusEvent
        self.assertEqual(len(self.records), 6)
        self.assertEqual([r.action for r in self.records],
                         ["DOWN", "UP", "DOWN", "DOWN", "DOWN", "UP"])

    def test_parse_extracts_name_and_keycode_together(self):
        first = self.records[0]
        self.assertEqual(first.key_name, "MENU")
        self.assertEqual(first.key_code, 82)
        self.assertEqual(first.scan_code, 139)
        self.assertEqual(first.action, "DOWN")
        self.assertEqual(first.device_id, 3)
        self.assertEqual(first.repeat_count, 0)

    def test_parse_handles_numeric_key_name(self):
        # 数字键在 dump 里名字位就是数字本身：keyCode=6(13)
        self.assertEqual(self.records[2].key_name, "6")
        self.assertEqual(self.records[2].key_code, 13)
        self.assertEqual(self.records[2].scan_code, 7)

    def test_parse_identifies_injected_events(self):
        injected = [r for r in self.records if not r.is_physical]
        self.assertEqual(len(injected), 2)
        self.assertTrue(all(r.device_id == -1 for r in injected))
        self.assertTrue(all(r.scan_code == 0 for r in injected))

    def test_identity_includes_action_so_injected_pair_stays_distinct(self):
        # 注入的 DOWN/UP 共用 eventTime，只用 eventTime 去重会把 UP 吞掉
        down, up = self.records[4], self.records[5]
        self.assertEqual(down.event_time, up.event_time)
        self.assertNotEqual(down.identity, up.identity)

    def test_parse_returns_empty_when_block_absent(self):
        self.assertEqual(parse_recent_queue("Input Dispatcher State:\n"), [])


class NullKeyNameTests(unittest.TestCase):
    """厂商键可能打印成 ``(null)``，正则需容忍并归一化成空串。"""

    def test_parse_normalizes_null_key_name(self):
        dump = (
            "  RecentQueue: length=1\n"
            "    KeyEvent(deviceId=13, eventTime=100, source=KEYBOARD, displayId=-1, "
            "action=DOWN, flags=0x0, keyCode=(null)(0), scanCode=453, "
            "metaState=0x0, repeatCount=0), policyFlags=0x0, age=1ms\n"
            "  PendingEvent: <none>\n"
        )
        records = parse_recent_queue(dump)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].key_name, "")
        self.assertEqual(records[0].key_code, 0)
        self.assertEqual(records[0].scan_code, 453)


class AutoRepeatTests(unittest.TestCase):
    """长按自动重复：真机上一条长按会灌满整个 RecentQueue。

    样本同样取自真机（按住 HOME 不放时的 ``dumpsys input``）。
    """

    _HELD_KEY_FIXTURE = """  RecentQueue: length=3
    KeyEvent(deviceId=12, eventTime=3845036995707, source=KEYBOARD | DPAD, displayId=-1, action=DOWN, flags=0x00000008, keyCode=HOME(3), scanCode=102, metaState=0x00000000, repeatCount=0), policyFlags=0x42000001, age=2222ms
    KeyEvent(deviceId=12, eventTime=3845088063749, source=KEYBOARD | DPAD, displayId=-1, action=DOWN, flags=0x00000008, keyCode=HOME(3), scanCode=102, metaState=0x00000000, repeatCount=1), policyFlags=0x42000001, age=2171ms
    KeyEvent(deviceId=12, eventTime=3845138733541, source=KEYBOARD | DPAD, displayId=-1, action=DOWN, flags=0x00000008, keyCode=HOME(3), scanCode=102, metaState=0x00000000, repeatCount=2), policyFlags=0x42000001, age=2120ms
  PendingEvent: <none>
"""

    def test_only_the_first_event_counts_as_an_initial_press(self):
        records = parse_recent_queue(self._HELD_KEY_FIXTURE)

        self.assertEqual([r.repeat_count for r in records], [0, 1, 2])
        self.assertEqual([r.is_initial_press for r in records], [True, False, False])

    def test_repeats_have_distinct_identity_so_dedup_alone_cannot_stop_them(self):
        records = parse_recent_queue(self._HELD_KEY_FIXTURE)

        self.assertEqual(len({r.identity for r in records}), 3)


class InputDevicesParserTests(unittest.TestCase):
    def setUp(self):
        self.devices = parse_input_devices(_DEVICES_FIXTURE)

    def test_parse_maps_device_id_to_name_and_path(self):
        self.assertEqual(len(self.devices), 4)
        self.assertEqual(self.devices[13].name, "TV BLE Remote Keyboard")
        self.assertEqual(self.devices[13].path, "/dev/input/event12")
        self.assertEqual(self.devices[3].path, "/dev/input/event8")

    def test_parse_marks_virtual_node_as_not_listenable(self):
        self.assertEqual(self.devices[9].path, "<virtual>")
        self.assertFalse(self.devices[9].is_event_node)
        self.assertTrue(self.devices[13].is_event_node)

    def test_parse_stops_at_next_section(self):
        # "Unattached video devices" 下的条目不能被当成输入设备
        self.assertEqual(sorted(self.devices), [1, 3, 9, 13])

    def test_parse_returns_empty_when_block_absent(self):
        self.assertEqual(parse_input_devices("Event Hub State:\n"), {})


if __name__ == "__main__":
    unittest.main()
