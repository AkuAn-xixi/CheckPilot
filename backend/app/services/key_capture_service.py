"""按键捕获：把「按一下遥控器」变成一条 keyname → keycode 映射。

数据来源是 ``adb shell dumpsys input`` 的 RecentQueue——InputDispatcher 会把最近
10 条事件连解析好的 keycode 名与数值一起留在这里，因此不需要任何静态映射表。

本服务**只读设备、只产出事件**，不写任何文件：落盘由调用方经既有接口完成，
这样服务对文件系统零依赖，也好测。

第三张表（``monitor_key_mappings.json``）的 source 键名必须取自 getevent 侧——
监听线程读的是 Linux 键名，与 dump 里的 Android 键名只有一部分重合，
``SCAN_xxxx`` 这类兜底名更是只能由 getevent 给出。故捕获期间并行跑一路 getevent 伴读，
按设备节点对齐两侧事件。
"""

from __future__ import annotations

import logging
import re
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple

from ..utils.adb_controller import ADBController
from ..utils.input_dump_parser import (
    InputDevice,
    InputReaderDevice,
    KeyEventRecord,
    parse_input_devices,
    parse_input_reader_devices,
    parse_recent_queue,
)

logger = logging.getLogger(__name__)


# Android keycode 名 → 本项目脚本词汇。
# 取值必须与 ``main.py`` 里 ``KEY_CUSTOM_MAPPING`` 的**取值侧**保持一致，否则监听序列
# 产出的键名会与 key_codes 里登记的键名对不上。未收录的键保留 Android 原名，
# 保存后仍可在客制化页改名。
ANDROID_TO_SCRIPT_KEYNAME: Dict[str, str] = {
    "DPAD_CENTER": "OK",
    "DPAD_UP": "UP",
    "DPAD_DOWN": "DOWN",
    "DPAD_LEFT": "LEFT",
    "DPAD_RIGHT": "RIGHT",
    "CHANNEL_UP": "CHUP",
    "CHANNEL_DOWN": "CHDOWN",
    "SETTINGS": "SETTING",
    "VOLUME_UP": "VOLUMEUP",
    "VOLUME_DOWN": "VOLUMEDOWN",
    "VOLUME_MUTE": "MUTE",
    "TV_INPUT": "SOURCE",
    "PROG_RED": "RED",
    "PROG_GREEN": "GREEN",
    "PROG_YELLOW": "YELLOW",
    "PROG_BLUE": "BLUE",
    "F1": "YOUTUBE",
    "F2": "NETFLIX",
    "F4": "PRIME_VIDEO",
}

# 数字键在 dump 里名字位就是数字本身（``keyCode=6(13)``），脚本里用 DIGITAL<n>。
_DIGIT_KEY_ALIAS_TEMPLATE = "DIGITAL{0}"

# 名字位无法解析时的兜底前缀，例如厂商键被打印成 ``keyCode=(null)(0)``。
_ANONYMOUS_KEY_TEMPLATE = "KEYCODE_{0}"

DEFAULT_POLL_INTERVAL = 0.4
_DUMP_TIMEOUT_SECONDS = 10.0

# RecentQueue 只有 10 条，窗口取大一些足以覆盖两轮轮询之间的所有事件。
_MAX_TRACKED_EVENTS = 200

# 连续这么多次 dumpsys 失败才结束会话：单次抖动（USB 重枚举、ADB server 忙）
# 不该把用户正在按键的会话直接判死。
_MAX_CONSECUTIVE_FAILURES = 5

# 同一拍内的取 dump 尝试次数与重试间隔。常驻的 getevent 伴读会让 adb 偶发
# "no devices/emulators found"（实测约 8%），而 RecentQueue 只存 10 条，
# 漏一拍就可能丢按键，所以失败要立刻重来而不是等下一拍。
_MAX_POLL_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 0.15

_ACTION_DOWN = "DOWN"
_ACTION_UP = "UP"
_KEY_ACTIONS = frozenset({_ACTION_DOWN, _ACTION_UP})
_KEY_PREFIX = "KEY_"
_UNKNOWN_KEY_NAMES = frozenset({"UNKNOWN", "RESERVED", ""})

_EV_KEY_TOKEN = "EV_KEY"
_MSC_SCAN_TOKEN = "MSC_SCAN"
_MSC_SCAN_LINE_MARKER = "EV_MSC"

# getevent -lt 的行前缀形如 ``[   123.456789] /dev/input/event8: EV_KEY ...``
_DEVICE_PREFIX_PATTERN = re.compile(r"\]\s+([^\s:]+):")

_PROCESS_EXIT_TIMEOUT_SECONDS = 2.0
_THREAD_JOIN_TIMEOUT_SECONDS = 3.0


class KeyCaptureError(RuntimeError):
    """按键捕获的会话级错误。"""


@dataclass(frozen=True)
class CapturedKey:
    """一次物理按键捕获到的全部信息。

    Attributes:
        seq: 会话内自增序号，供前端增量拉取。
        device_id: dispatcher 的设备序号。
        device_name: 来源设备名，如 ``TV BLE Remote Keyboard``。
        device_path: 来源设备节点，如 ``/dev/input/event12``。
        android_keyname: dump 里的 keycode 名，如 ``SETTINGS``。
        android_keycode: Android keycode 数值。
        script_keyname: 按别名表转换后的脚本侧键名。
        linux_scan_code: Linux 输入码，可直接作为 sendevent 的目标码。
        monitor_source_key: 监听线程对该键实际产出的键名（如 ``SCAN_C0085``）；
            伴读未对齐上时为 None。
        is_paired: 是否成功与 getevent 侧对齐。
        captured_at: 捕获时刻（Unix 秒）。
    """

    seq: int
    device_id: int
    device_name: str
    device_path: str
    android_keyname: str
    android_keycode: int
    script_keyname: str
    linux_scan_code: int
    monitor_source_key: Optional[str]
    is_paired: bool
    captured_at: float

    @property
    def has_usable_keycode(self) -> bool:
        """keycode 是否能真的发出去。

        kl 未收录的厂商键会被解析成 ``KEYCODE_UNKNOWN(0)``，这种键写进 key_codes
        也没有意义（``send_keyevent`` 要求 1..999），只能靠第三张表按 ``SCAN_`` 纠错。
        """
        return self.android_keycode > 0

    def to_dict(self) -> Dict[str, Any]:
        """转成可直接 JSON 化的字典（额外带上派生标记，省得前端再算一遍）。"""
        return {
            "seq": self.seq,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "device_path": self.device_path,
            "android_keyname": self.android_keyname,
            "android_keycode": self.android_keycode,
            "script_keyname": self.script_keyname,
            "linux_scan_code": self.linux_scan_code,
            "monitor_source_key": self.monitor_source_key,
            "is_paired": self.is_paired,
            "has_usable_keycode": self.has_usable_keycode,
            "captured_at": self.captured_at,
        }


def resolve_script_keyname(android_keyname: str, android_keycode: int) -> str:
    """把 Android keycode 名翻成本项目脚本词汇。

    Args:
        android_keyname: dump 里的 keycode 名，如 ``DPAD_CENTER``；可能为空串。
        android_keycode: keycode 数值，名字无法解析时用它兜底命名。

    Returns:
        脚本侧键名；未收录时保留 Android 原名。
    """
    normalized = android_keyname.strip().upper()
    if not normalized:
        return _ANONYMOUS_KEY_TEMPLATE.format(android_keycode)
    if normalized.isdigit():
        return _DIGIT_KEY_ALIAS_TEMPLATE.format(normalized)
    return ANDROID_TO_SCRIPT_KEYNAME.get(normalized, normalized)


def extract_getevent_device_path(line: str) -> str:
    """取出 getevent 行前缀里的设备节点，如 ``/dev/input/event8``。

    Args:
        line: getevent 的一行输出。

    Returns:
        设备节点路径；取不到时返回空串。
    """
    match = _DEVICE_PREFIX_PATTERN.search(line)
    return match.group(1) if match else ""


def parse_getevent_line(
    line: str, pending_msc_scan: Optional[str]
) -> Tuple[Optional[str], Optional[str]]:
    """解析一行 ``getevent -lt`` 输出，取按键名。

    解析口径与 ``main.py`` 中的监听线程保持一致：蓝牙 HID 遥控器很多按键被映射成
    ``KEY_UNKNOWN``/``KEY_RESERVED``，此时 EV_KEY 无法区分按键，必须用前一条
    ``EV_MSC MSC_SCAN`` 兜底成 ``SCAN_<去前导零并大写>``。

    Args:
        line: getevent 的一行输出。
        pending_msc_scan: 上一条 MSC_SCAN 的原始值，供紧随其后的 EV_KEY 使用。

    Returns:
        ``(按键名, 新的 MSC_SCAN 缓存)``。按键名仅在按下（DOWN）时非 None。
    """
    if _MSC_SCAN_LINE_MARKER in line and _MSC_SCAN_TOKEN in line:
        return None, _extract_msc_scan(line)

    if _EV_KEY_TOKEN not in line:
        return None, pending_msc_scan

    key_name, status = _extract_key_tokens(line)
    if key_name is None or status.upper() != _ACTION_DOWN:
        # 松开事件也要把 MSC_SCAN 消费掉，避免留给下一个按键误用
        return None, None

    simplified = key_name.replace(_KEY_PREFIX, "")
    if simplified.upper() in _UNKNOWN_KEY_NAMES and pending_msc_scan:
        simplified = f"SCAN_{pending_msc_scan.lstrip('0').upper() or '0'}"
    return simplified, None


def _extract_key_action(line: str) -> Optional[str]:
    """取出 ``EV_KEY`` 行的按下/抬起状态。

    Returns:
        ``"DOWN"`` / ``"UP"``；非 EV_KEY 行或状态字段异常时返回 None。
    """
    if _EV_KEY_TOKEN not in line:
        return None
    _, status = _extract_key_tokens(line)
    normalized = status.upper()
    return normalized if normalized in _KEY_ACTIONS else None


def _extract_msc_scan(line: str) -> Optional[str]:
    """取出 ``MSC_SCAN`` 后面的十六进制值，如 ``000c0085``。"""
    parts = line.split()
    for index, part in enumerate(parts):
        if part == _MSC_SCAN_TOKEN and index + 1 < len(parts):
            return parts[index + 1]
    return None


def _extract_key_tokens(line: str) -> Tuple[Optional[str], str]:
    """取出 ``EV_KEY`` 之后的名字与状态两个字段。"""
    parts = line.split()
    for index, part in enumerate(parts):
        if part == _EV_KEY_TOKEN and index + 2 < len(parts):
            return parts[index + 1], parts[index + 2]
    return None, ""


class KeyCaptureService:
    """捕获会话的生命周期管理。

    - :meth:`start` 会先吃掉队列里的陈旧事件，否则一开capture就会把历史按键灌进配置。
    - 只保留 ``deviceId >= 0`` 的按下事件，本工具自己 injection 的按键不会被记进来。
    - getevent 伴读起不来时主流程照常跑，只是第三张表留空。
    """

    def __init__(self, adb: ADBController, *, poll_interval: float = DEFAULT_POLL_INTERVAL) -> None:
        self._adb = adb
        self._poll_interval = poll_interval

        self._lock = threading.Lock()
        self._raw_lock = threading.Lock()

        self._events: List[CapturedKey] = []
        # Event Hub 编号 → 节点；用于把 Reader 设备还原成 /dev/input/eventN
        self._devices: Dict[int, InputDevice] = {}
        # Reader 编号 → 设备；RecentQueue 的 deviceId 用的是这一套
        self._reader_devices: Dict[int, InputReaderDevice] = {}
        self._seen: set = set()
        self._seen_order: Deque[Tuple[int, int, str]] = deque()

        self._is_running = False
        # 两类错误分开存：轮询失败是可恢复的（下一次成功即清除），
        # 伴读失败在本次会话内不可恢复（一直显示到会话结束）。
        self._poll_error = ""
        self._companion_error = ""
        self._stop_event = threading.Event()
        self._poller: Optional[threading.Thread] = None
        self._companion: Optional[threading.Thread] = None
        self._companion_process: Optional[subprocess.Popen] = None

        # 设备节点 → 待配对的 getevent 原始键名
        self._raw_names: Dict[str, Deque[str]] = {}
        # 设备节点 → 该设备当前按着未抬起的键名，用于识别长按自动重复
        self._raw_last_key: Dict[str, str] = {}

    # ───────────────────── 会话生命周期 ─────────────────────

    def start(self) -> None:
        """开启捕获会话。

        Raises:
            KeyCaptureError: 已有会话在进行，或读取设备状态失败。
        """
        if self._is_running:
            raise KeyCaptureError("捕获会话已在进行中")

        self._reset_session()
        self._prime_baseline()

        self._stop_event.clear()
        self._is_running = True
        self._companion = threading.Thread(target=self._run_companion, daemon=True)
        self._companion.start()
        self._poller = threading.Thread(target=self._run_poller, daemon=True)
        self._poller.start()
        logger.info("按键捕获已开始")

    def stop(self) -> None:
        """结束捕获会话并等待两个读线程收工。

        幂等：会话因设备出错自行停下后前端仍可能补一次停止，这里直接返回而不是报错。
        """
        if not self._is_running:
            return

        self._stop_event.set()
        # 先掐掉伴读进程：它的 stdout 会被 readline 阻塞，不结束它线程join不回来
        self._terminate_companion(self._take_companion_process())

        for thread in (self._companion, self._poller):
            if thread is not None:
                thread.join(timeout=_THREAD_JOIN_TIMEOUT_SECONDS)
        self._companion = None
        self._poller = None

        with self._lock:
            self._is_running = False
        logger.info("按键捕获已结束，共捕获 %d 条", len(self._events))

    def status(self) -> Dict[str, Any]:
        """返回会话状态，供前端显示与轮询。"""
        with self._lock:
            return {
                "is_running": self._is_running,
                "event_count": len(self._events),
                "latest_seq": self._events[-1].seq if self._events else 0,
                "last_error": self._companion_error or self._poll_error,
                "sources": [
                    {
                        "device_id": device_id,
                        "name": name,
                        "paths": self._candidate_paths(device_id),
                    }
                    for device_id, name in sorted(self._device_catalog())
                ],
            }

    def list_events(self, since_seq: int = 0) -> Dict[str, Any]:
        """取出序号大于 ``since_seq`` 的捕获结果。

        Args:
            since_seq: 前端上次拿到的最大序号，首次传 0。

        Returns:
            ``{"events": [...], "latest_seq": int}``。
        """
        with self._lock:
            events = [item.to_dict() for item in self._events if item.seq > since_seq]
            latest_seq = self._events[-1].seq if self._events else 0
        return {"events": events, "latest_seq": latest_seq}

    # ───────────────────── 读线程 ─────────────────────

    def _run_poller(self) -> None:
        """轮询 dumpsys input，把新出现的物理按键转成捕获结果。

        单次 adb 抖动（USB 重新枚举、ADB server 忙）不该直接废掉整场会话，
        连续失败到阈值才收工，最后一次的错误留在 ``status().last_error`` 里。
        """
        consecutive_failures = 0
        while not self._stop_event.is_set():
            try:
                self._poll_once()
                consecutive_failures = 0
            except KeyCaptureError as e:
                consecutive_failures += 1
                self._record_poll_error(str(e))
                if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                    break
            self._stop_event.wait(self._poll_interval)
        with self._lock:
            self._is_running = False

    def _run_companion(self) -> None:
        """并行读 getevent，记录监听线程对该设备真正产出的键名。"""
        process: Optional[subprocess.Popen] = None
        try:
            process = self._adb.spawn_shell_stream("getevent", "-lt")
            with self._lock:
                self._companion_process = process
            self._consume_getevent_stream(process)
        except (RuntimeError, OSError, ValueError) as e:
            self._record_companion_error(f"getevent 伴读不可用，监听键名将留空: {e}")
        finally:
            self._terminate_companion(self._take_companion_process())

    def _consume_getevent_stream(self, process: subprocess.Popen) -> None:
        """逐行消费 getevent 输出，按设备节点分桶缓存原始键名。"""
        pending_msc_scan: Optional[str] = None
        if process.stdout is None:
            return

        for line in process.stdout:
            if self._stop_event.is_set():
                return
            key_name, pending_msc_scan = parse_getevent_line(line, pending_msc_scan)
            device_path = extract_getevent_device_path(line)
            if not device_path or not self._is_fresh_press(line, device_path, key_name):
                continue
            if key_name is None:
                continue
            with self._raw_lock:
                self._raw_names.setdefault(device_path, deque()).append(key_name)

    def _is_fresh_press(self, line: str, device_path: str, key_name: Optional[str]) -> bool:
        """判断这行输出是否为「一次新按下」，同时维护每个设备的长按状态。

        长按时内核每 ~50ms 就重复报一条同名 DOWN、中间没有 UP。只收同设备同键名的
        第一条，否则一次长按会在待配对队列里堆出好几条，让 :meth:`_take_raw_name`
        判定成歧义而放弃配对。抬起后清掉记录，下一次按下重新算首发。

        两次**不同**键名的快速连按不会被这里合并，仍会留给 ``_take_raw_name``
        去判歧义——那种情况确实无法判断谁对应谁。

        调用方必须已确认 ``device_path`` 非空。
        """
        action = _extract_key_action(line)
        if action is None:
            return False
        with self._raw_lock:
            if action == _ACTION_UP:
                self._raw_last_key.pop(device_path, None)
                return False
            if key_name is None or self._raw_last_key.get(device_path) == key_name:
                return False
            self._raw_last_key[device_path] = key_name
            return True

    # ───────────────────── 轮询与配对 ─────────────────────

    def _poll_once(self) -> None:
        """抓一次 dump，更新设备表并处理新事件。"""
        dump = self._fetch_dump_with_retry()
        with self._lock:
            self._poll_error = ""

        devices = parse_input_devices(dump)
        reader_devices = parse_input_reader_devices(dump)
        with self._lock:
            if devices:
                self._devices = devices
            if reader_devices:
                self._reader_devices = reader_devices

        for record in parse_recent_queue(dump):
            self._handle_record(record)

    def _handle_record(self, record: KeyEventRecord) -> None:
        """过滤掉已见过的事件与非物理设备事件，其余落成捕获结果。

        长按会持续产生 DOWN（``repeatCount`` 递增、``eventTime`` 各不相同），
        只按 ``identity`` 去重会把一次长按记成几十条，所以只收首发事件。
        """
        with self._lock:
            if record.identity in self._seen:
                return
            self._remember(record.identity)

        if not record.is_physical or record.action != _ACTION_DOWN:
            return
        if not record.is_initial_press:
            return
        self._append_captured(record)

    def _append_captured(self, record: KeyEventRecord) -> None:
        """把一条按下事件连同来源设备、监听键名一起记下来。"""
        with self._lock:
            device_name = self._device_name(record.device_id)
            candidate_paths = self._candidate_paths(record.device_id)

        source_key, matched_path = self._take_raw_name(candidate_paths)
        if not matched_path and len(candidate_paths) == 1:
            # 只有唯一候选节点时，即使没配对上键名，来源节点也是确定的
            matched_path = candidate_paths[0]

        with self._lock:
            self._events.append(
                CapturedKey(
                    seq=len(self._events) + 1,
                    device_id=record.device_id,
                    device_name=device_name,
                    device_path=matched_path,
                    android_keyname=record.key_name,
                    android_keycode=record.key_code,
                    script_keyname=resolve_script_keyname(record.key_name, record.key_code),
                    linux_scan_code=record.scan_code,
                    monitor_source_key=source_key,
                    is_paired=source_key is not None,
                    captured_at=time.time(),
                )
            )

    def _device_catalog(self) -> List[Tuple[int, str]]:
        """返回 ``[(device_id, 设备名)]``，优先用 Input Reader 那套编号。

        只列出有可监听节点的设备：``Virtual`` 这类没有 ``/dev/input/eventN`` 的
        设备既不会产生可捕获的按键，列在界面上只会添乱。

        调用方必须持有 ``self._lock``。
        """
        if self._reader_devices:
            catalog = [(item.device_id, item.name) for item in self._reader_devices.values()]
        else:
            catalog = [(item.device_id, item.name) for item in self._devices.values()]
        return [item for item in catalog if self._candidate_paths(item[0])]

    def _device_name(self, device_id: int) -> str:
        """取该 dispatcher 设备的显示名；取不到时返回空串。

        调用方必须持有 ``self._lock``。
        """
        reader = self._reader_devices.get(device_id)
        if reader is not None:
            return reader.name
        node = self._devices.get(device_id)
        return node.name if node is not None else ""

    def _candidate_paths(self, device_id: int) -> List[str]:
        """列出该 dispatcher 设备可能对应的 Event Hub 节点。

        一个 Reader 设备会把同一个物理 HID 的多个节点（键盘 + 多媒体键）合并成一个，
        事件具体从哪个节点来无法预知，所以候选全带上，交给待配对的键名去挑。

        调用方必须持有 ``self._lock``。
        """
        reader = self._reader_devices.get(device_id)
        if reader is None:
            # 拿不到 Input Reader State 时退回 Event Hub 编号（老版本 / 段落缺失）
            return self._event_node_paths([device_id])
        return self._event_node_paths(reader.event_hub_ids)

    def _event_node_paths(self, node_ids: Iterable[int]) -> List[str]:
        """把 Event Hub 编号过滤成可监听的 ``/dev/input/eventN``。

        调用方必须持有 ``self._lock``。
        """
        paths = []
        for node_id in node_ids:
            node = self._devices.get(node_id)
            if node is not None and node.is_event_node:
                paths.append(node.path)
        return paths

    def _take_raw_name(self, device_paths: List[str]) -> Tuple[Optional[str], str]:
        """从候选节点里取走待配对的 getevent 键名。

        同一轮次里攒了多条说明按键挨得太近、无法判断谁对应谁，此时**不猜**：
        整批丢弃并返回空，让界面留空给用户手填。

        Args:
            device_paths: 该事件可能来源的设备节点。

        Returns:
            ``(监听键名, 命中的设备节点)``；未配对时为 ``(None, "")``。
        """
        with self._raw_lock:
            names: List[str] = []
            matched_path = ""
            for path in device_paths:
                queue = self._raw_names.get(path)
                if not queue:
                    continue
                names.extend(queue)
                matched_path = matched_path or path
                queue.clear()
            if len(names) != 1:
                return None, ""
            return names[0], matched_path

    # ───────────────────── 内部工具 ─────────────────────

    def _fetch_dump(self) -> str:
        """读取一次 ``dumpsys input``。

        Raises:
            KeyCaptureError: adb 调用失败或超时。
        """
        try:
            return self._adb.run_shell_command("dumpsys", "input", timeout=_DUMP_TIMEOUT_SECONDS)
        except RuntimeError as e:
            raise KeyCaptureError(f"读取 dumpsys input 失败: {e}") from e

    def _fetch_dump_with_retry(self) -> str:
        """取一次 dump，失败就立刻重试，全部失败才抛出最后一次的异常。

        Raises:
            KeyCaptureError: 连续 ``_MAX_POLL_ATTEMPTS`` 次都失败。
        """
        attempts = 0
        while True:
            try:
                return self._fetch_dump()
            except KeyCaptureError:
                attempts += 1
                if attempts >= _MAX_POLL_ATTEMPTS:
                    raise
                self._stop_event.wait(_RETRY_BACKOFF_SECONDS)

    def _prime_baseline(self) -> None:
        """先把队列里已有的事件记为「已见过」，避免陈旧按键被当成新捕获。

        Raises:
            KeyCaptureError: 首次读取设备状态失败。
        """
        dump = self._fetch_dump_with_retry()
        devices = parse_input_devices(dump)
        reader_devices = parse_input_reader_devices(dump)
        with self._lock:
            self._devices = devices
            self._reader_devices = reader_devices
            for record in parse_recent_queue(dump):
                self._remember(record.identity)

    def _reset_session(self) -> None:
        """清空上一轮会话的残留状态。"""
        with self._lock:
            self._events = []
            self._seen = set()
            self._seen_order = deque()
            self._poll_error = ""
            self._companion_error = ""
        with self._raw_lock:
            self._raw_names = {}
            self._raw_last_key = {}
        self._take_companion_process()

    def _remember(self, identity: Tuple[int, int, str]) -> None:
        """记住一个已处理事件；窗口满了就淘汰最旧的，避免集合无限增长。

        调用方必须持有 ``self._lock``。
        """
        self._seen.add(identity)
        self._seen_order.append(identity)
        while len(self._seen_order) > _MAX_TRACKED_EVENTS:
            self._seen.discard(self._seen_order.popleft())

    def _take_companion_process(self) -> Optional[subprocess.Popen]:
        """取出并清空伴读进程句柄，保证只会被终止一次。"""
        with self._lock:
            process = self._companion_process
            self._companion_process = None
        return process

    def _terminate_companion(self, process: Optional[subprocess.Popen]) -> None:
        """结束伴读进程；失败只记录不抛出，避免掩盖真正的会话错误。"""
        if process is None:
            return
        try:
            process.terminate()
            process.wait(timeout=_PROCESS_EXIT_TIMEOUT_SECONDS)
        except (OSError, subprocess.TimeoutExpired) as e:
            self._record_companion_error(f"结束 getevent 伴读进程失败: {e}")
        finally:
            if process.stdout is not None:
                process.stdout.close()

    def _record_poll_error(self, message: str) -> None:
        """记录一次轮询失败。

        它反映的是「此刻还读不读得到设备」，所以下一次成功轮询会把它清掉；
        否则一次 USB 抖动留下的错误会一直挂在界面上，看起来像坏了。
        """
        logger.warning("按键捕获: %s", message)
        with self._lock:
            self._poll_error = message

    def _record_companion_error(self, message: str) -> None:
        """记录伴读异常。伴读起不来在本次会话内不可恢复，因此一直保留。"""
        logger.warning("按键捕获: %s", message)
        with self._lock:
            self._companion_error = message
