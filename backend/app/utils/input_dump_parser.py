"""``adb shell dumpsys input`` 输出的纯解析工具。

按键捕获依赖这份 dump 里的两个区块：

- ``RecentQueue``（Input Dispatcher State 下）：最近 10 条事件，每条自带解析好的
  Android keycode 名与数值，是「keyname → keycode」的权威来源，无需任何静态映射表。
- ``Devices``（Event Hub State 下）：``索引: 设备名`` 的索引就是 dispatcher 使用的
  ``deviceId``，且每条带 ``Path: /dev/input/eventN``，用于和 ``getevent`` 输出对齐。

本模块只做「字符串 → 数据类」的转换，不碰 adb，便于单元测试。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Dict, Iterator, List, Optional, Tuple


# 区块内的行至少缩进 4 空格；回到更浅的缩进即视为区块结束。
_BLOCK_MIN_INDENT = 4

# 区块起始标记（都是 2 空格缩进，且首行带额外内容，故用 startswith 匹配）。
_RECENT_QUEUE_HEADER = "  RecentQueue:"
_DEVICES_HEADER = "  Devices:"

# 单条 KeyEvent。key_name 用惰性匹配，以兼容厂商键打印成 ``keyCode=(null)(0)`` 的情况
# （此时名字位是 "(null)"）；实测本机越界 keycode 会退化成 ``UNKNOWN(0)``。
_KEY_EVENT_PATTERN = re.compile(
    r"KeyEvent\(deviceId=(?P<device_id>-?\d+),"
    r" eventTime=(?P<event_time>\d+),"
    r".*?action=(?P<action>DOWN|UP),"
    r".*?keyCode=(?P<key_name>.*?)\((?P<key_code>\d+)\),"
    r".*?scanCode=(?P<scan_code>\d+),"
    r".*?repeatCount=(?P<repeat_count>\d+)"
)

_DEVICE_HEADER_PATTERN = re.compile(r"^ {4}(\d+): (.+?)\s*$")
_DEVICE_PATH_PATTERN = re.compile(r"^ {6}Path: (\S+)$")

# Input Reader State 用 0 缩进的标题，其设备条目只缩进 2 空格。
_INPUT_READER_HEADER = "Input Reader State"
_READER_DEVICE_PATTERN = re.compile(r"^ {2}Device (-?\d+): (.+?)\s*$")
_READER_EVENT_HUB_PATTERN = re.compile(r"^ {4}EventHub Devices: \[(.*?)\]")

# 名字位是 "(null)" 时归一化成空串，由调用方决定怎么兜底命名。
_NULL_KEY_NAME = "(null)"

# ``deviceId = -1`` 表示经 ``input keyevent`` 注入，不是物理设备。
_INJECTED_DEVICE_ID = -1

# 真实的输入设备节点前缀；``<virtual>`` / ``<none>`` 这类占位值不算。
_EVENT_NODE_PREFIX = "/dev/input/"

# 一次按下的首发事件，其 repeatCount 必为 0；长按重复会从 1 开始递增。
_INITIAL_REPEAT_COUNT = 0


@dataclass(frozen=True)
class KeyEventRecord:
    """RecentQueue 里的一条按键事件。

    Attributes:
        device_id: dispatcher 的设备序号；-1 表示由 ``input keyevent`` 注入。
        event_time: 事件时间戳（纳秒）。注入事件的 DOWN/UP 会共用同一个值，
            所以去重不能只看它。
        action: ``DOWN`` 或 ``UP``。
        key_name: Android keycode 名，如 ``HOME``；无法解析时为空串。
        key_code: Android keycode 数值。
        scan_code: Linux 输入码，可直接作为 sendevent 的目标码；注入事件恒为 0。
        repeat_count: 长按自动重复的计数；首次按下为 0。
    """

    device_id: int
    event_time: int
    action: str
    key_name: str
    key_code: int
    scan_code: int
    repeat_count: int

    @property
    def identity(self) -> Tuple[int, int, str]:
        """事件去重用的身份。必须含 action，否则注入的 DOWN/UP 会被当成同一条。"""
        return (self.device_id, self.event_time, self.action)

    @property
    def is_physical(self) -> bool:
        """是否为物理设备产生的事件（用于排除本工具自身注入的按键）。"""
        return self.device_id != _INJECTED_DEVICE_ID

    @property
    def is_initial_press(self) -> bool:
        """是否为一次按下的「首发」事件，而非长按自动重复。

        长按时内核每 ~50ms 补一条 DOWN，它们 eventTime 各不相同，只靠
        ``identity`` 去重会把一次长按记成几十条捕获结果。
        """
        return self.repeat_count == _INITIAL_REPEAT_COUNT


@dataclass(frozen=True)
class InputDevice:
    """Event Hub State 里的一台输入设备。

    Attributes:
        device_id: 与 :class:`KeyEventRecord` 的 device_id 同一套编号。
        name: 设备名，如 ``TV BLE Remote Keyboard``。
        path: ``/dev/input/eventN``；纯开关类节点没有该字段，此时为空串。
    """

    device_id: int
    name: str
    path: str

    @property
    def is_event_node(self) -> bool:
        """是否为可直接 ``getevent`` 监听的设备节点（虚拟节点如 ``<virtual>`` 不是）。"""
        return self.path.startswith(_EVENT_NODE_PREFIX)


@dataclass(frozen=True)
class InputReaderDevice:
    """Input Reader State 里的一台设备；其编号才是 InputDispatcher 的 ``deviceId``。

    这一层和 Event Hub 的编号**不是同一套**，而且一个 Reader 设备会把同一个物理
    HID 设备的多个 application collection（例如 BLE 遥控器的 Keyboard 与 Consumer
    Control 两个节点）合并成一个，所以编号是一对多的。

    Attributes:
        device_id: ``KeyEventRecord.device_id`` 用的编号。
        name: 设备名，如 ``TV BLE Remote Consumer Control``。
        event_hub_ids: 合成该设备的 Event Hub 节点编号；用它去查 :class:`InputDevice`
            才能拿到 ``/dev/input/eventN``。
    """

    device_id: int
    name: str
    event_hub_ids: Tuple[int, ...]


def parse_recent_queue(dump_text: str) -> List[KeyEventRecord]:
    """解析 RecentQueue 里的按键事件，按 dump 中的先后顺序返回。

    ``FocusEvent`` 等非按键条目会被跳过。

    Args:
        dump_text: ``adb shell dumpsys input`` 的完整输出。

    Returns:
        按键事件列表；找不到 RecentQueue 区块时返回空列表。
    """
    records: List[KeyEventRecord] = []
    for line in _iter_indented_block(dump_text, _RECENT_QUEUE_HEADER):
        match = _KEY_EVENT_PATTERN.search(line)
        if match is None:
            continue
        key_name = match.group("key_name").strip()
        records.append(
            KeyEventRecord(
                device_id=int(match.group("device_id")),
                event_time=int(match.group("event_time")),
                action=match.group("action"),
                key_name="" if key_name == _NULL_KEY_NAME else key_name,
                key_code=int(match.group("key_code")),
                scan_code=int(match.group("scan_code")),
                repeat_count=int(match.group("repeat_count")),
            )
        )
    return records


def parse_input_devices(dump_text: str) -> Dict[int, InputDevice]:
    """解析 Event Hub State 的设备列表。

    Args:
        dump_text: ``adb shell dumpsys input`` 的完整输出。

    Returns:
        ``{device_id: InputDevice}``；缺少 ``Path`` 的设备也会收录，其 ``path`` 为空串。
    """
    devices: Dict[int, InputDevice] = {}
    current_id: Optional[int] = None

    for line in _iter_indented_block(dump_text, _DEVICES_HEADER):
        header = _DEVICE_HEADER_PATTERN.match(line)
        if header is not None:
            current_id = int(header.group(1))
            devices[current_id] = InputDevice(current_id, header.group(2), "")
            continue

        path = _DEVICE_PATH_PATTERN.match(line)
        if path is not None and current_id is not None:
            devices[current_id] = replace(devices[current_id], path=path.group(1))

    return devices


def parse_input_reader_devices(dump_text: str) -> Dict[int, InputReaderDevice]:
    """解析 Input Reader State 的设备列表。

    这是 ``RecentQueue`` 里 ``deviceId`` 的权威来源：Event Hub 的编号是另一套，
    实测同一个 BLE 遥控器的两个节点会被 Reader 合并成一个 ``Device 12``。

    Args:
        dump_text: ``adb shell dumpsys input`` 的完整输出。

    Returns:
        ``{device_id: InputReaderDevice}``；缺 ``EventHub Devices`` 行时其编号列表为空。
    """
    devices: Dict[int, InputReaderDevice] = {}
    current_id: Optional[int] = None

    for line in _iter_section_lines(dump_text, _INPUT_READER_HEADER):
        header = _READER_DEVICE_PATTERN.match(line)
        if header is not None:
            current_id = int(header.group(1))
            devices[current_id] = InputReaderDevice(current_id, header.group(2), ())
            continue

        hub = _READER_EVENT_HUB_PATTERN.match(line)
        if hub is not None and current_id is not None:
            node_ids = tuple(int(part) for part in hub.group(1).split())
            devices[current_id] = replace(devices[current_id], event_hub_ids=node_ids)

    return devices


def _iter_section_lines(dump_text: str, header: str) -> Iterator[str]:
    """迭代某个顶层区块（标题 0 缩进）之后、下一个顶层行之前的每一行。

    Args:
        dump_text: 待扫描的 dump 文本。
        header: 区块标题前缀，例如 ``"Input Reader State"``。

    Yields:
        区块内的每一行（不含标题行本身）。
    """
    is_inside = False
    for line in dump_text.splitlines():
        if not is_inside:
            is_inside = line.startswith(header)
            continue
        if not line.strip():
            continue
        # 遇到下一个顶层标题即说明本区块结束
        if not line.startswith(" "):
            return
        yield line


def _iter_indented_block(dump_text: str, header: str) -> Iterator[str]:
    """迭代 ``header`` 之后缩进不少于 4 空格的连续行。

    Args:
        dump_text: 待扫描的 dump 文本。
        header: 区块起始行前缀，例如 ``"  RecentQueue:"``。

    Yields:
        区块内的每一行（不含起始行本身）。
    """
    is_inside = False
    for line in dump_text.splitlines():
        if not is_inside:
            is_inside = line.startswith(header)
            continue
        if not line.strip():
            continue
        # 回到更浅的缩进说明区块已结束，下一行属于别的段落
        if len(line) - len(line.lstrip()) < _BLOCK_MIN_INDENT:
            return
        yield line
