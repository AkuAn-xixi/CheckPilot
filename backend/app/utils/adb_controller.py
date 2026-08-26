"""ADB控制器工具模块"""
import subprocess
import time
import os
import random
import re
import shlex
import json
import logging
import threading
from datetime import datetime
import pandas as pd
from typing import List, Optional, Dict, Any
from ..config import settings
from ...FieldValidation import get_valid_keys as get_runtime_valid_keys

logger = logging.getLogger(__name__)


KEYCODE_MAP = {
    "OK": 23,
    "HOME": 3,
    "BACK": 4,
    "UP": 19,
    "DOWN": 20,
    "LEFT": 21,
    "RIGHT": 22,
    "MENU": 82,
    "SETTING": 176,
    "SRTTING": 176,
    "DIGITAL0": 7,
    "DIGITAL1": 8,
    "DIGITAL2": 9,
    "DIGITAL3": 10,
    "DIGITAL4": 11,
    "DIGITAL5": 12,
    "DIGITAL6": 13,
    "DIGITAL7": 14,
    "DIGITAL8": 15,
    "DIGITAL9": 16,
    "APPS": 360,
    "POWER": 26,
    "SOURCE": 178,
    "CHUP": 82,
    "CHDOWN": 166,
    "EXIT": 167,
    "LIBRARY": 358,
    "DISCOVERY": 358,
    "TV_AV": 24,
    "VOLUMEUP": 24,
    "VOLUMEDOWN": 25,
    "NETFLIX": 132,
    "YOUTUBE": 131,
    "PRIME_VIDEO": 134,
    "PRIME_VII": 134,
    "ACTION3": 222,
    "ACTIONS": 222,
    "FILES": 359,
    "RED": 1,
    "GREEN": 2,
    "YELLOW": 3,
    "BLUE": 4,
    "INFORMATION": 7,
    "MUTE": 164,
    # ASSERT 是步骤分隔/断言占位符，不发实际 keyevent，但要被校验/解析当成有效按键。
    # 实际执行时会被 NON_EXECUTABLE_KEYS 拦截跳过，keycode 0 仅作占位。
    "ASSERT": 0,
    # NOTASSERT 是反向断言占位符：要求截图"不匹配"目标图标才算 PASS。
    # 与 ASSERT 一样不发 keyevent，仅被解析层识别、执行层接管校验。
    "NOTASSERT": 0,
    # TTS 标记：触发 ASR 校验流程，不发实际 keyevent。
    "TTS": 0,
}

# Android keycode → Linux input-event-codes keycode 映射（用于 sendevent 长按）。
# 仅覆盖常用按键；未列出的可通过 customization.json 的 sendevent_keycode_overrides 补充。
ANDROID_TO_LINUX_KEYCODE: Dict[int, int] = {
    3: 102,    # HOME → KEY_HOME
    4: 158,    # BACK → KEY_BACK
    7: 11,     # DIGITAL0 / KEY_0
    8: 2,      # DIGITAL1 / KEY_1
    9: 3,      # DIGITAL2 / KEY_2
    10: 4,     # DIGITAL3 / KEY_3
    11: 5,     # DIGITAL4 / KEY_4
    12: 6,     # DIGITAL5 / KEY_5
    13: 7,     # DIGITAL6 / KEY_6
    14: 8,     # DIGITAL7 / KEY_7
    15: 9,     # DIGITAL8 / KEY_8
    16: 10,    # DIGITAL9 / KEY_9
    19: 103,   # DPAD_UP → KEY_UP
    20: 108,   # DPAD_DOWN → KEY_DOWN
    21: 105,   # DPAD_LEFT → KEY_LEFT
    22: 106,   # DPAD_RIGHT → KEY_RIGHT
    23: 97,    # DPAD_CENTER / OK → KEY_ENTER
    24: 115,   # VOLUME_UP → KEY_VOLUMEUP
    25: 114,   # VOLUME_DOWN → KEY_VOLUMEDOWN
    26: 116,   # POWER → KEY_POWER
    82: 139,   # MENU → KEY_MENU
    131: 0x8a, # NETFLIX → KEY_BOOKMARKS (示例)
    132: 0x8b, # YOUTUBE → KEY_MEDIA
    134: 0x8c, # PRIME_VIDEO → KEY_SEARCH
    164: 113,  # MUTE → KEY_MUTE
    166: 402,  # CHANNEL_UP → KEY_CHANNELUP
    167: 403,  # CHANNEL_DOWN → KEY_CHANNELDOWN
    176: 353,  # SETTINGS → KEY_CONFIG
    178: 0x16a,# SOURCE → KEY_REFRESH (示例)
    222: 0x161,# ACTION3 → KEY_BOOKMARKS
    358: 0x166,# LIBRARY → KEY_INFO
    359: 0x167,# FILES → KEY_FINANCE
    360: 0x16b,# APPS → KEY_BOOKMARKS
}

# 这些"有效按键"在解析层是合法的，但执行时不发 adb keyevent。
# NOTASSERT 与 ASSERT 一样是校验占位符，只是语义取反（要求不匹配）。
NON_EXECUTABLE_KEYS = frozenset({"ASSERT", "TTS", "NOTASSERT"})

# sendevent 长按自动补齐：当配置的长按时长低于设备长按判定阈值时，
# 自动延长到「阈值 + 该裕量」，确保被 Android InputDispatcher 识别为长按。
SENDEVENT_LONG_PRESS_MARGIN_US = 150000  # 150ms
# 无法从设备查询到长按阈值时使用的兜底默认值（微秒）。
SENDEVENT_LONG_PRESS_DEFAULT_TIMEOUT_US = 500000  # 500ms


def get_keycode_map() -> dict:
    """返回合并后的键值映射：KEYCODE_MAP 默认值 + 当前激活方案的 key_codes 覆盖。"""
    merged = dict(KEYCODE_MAP)
    try:
        path = settings.CUSTOMIZATION_FILE
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 同时兼容旧扁平格式和新方案格式
            if "schemes" in data:
                active = data.get("active_scheme", "默认")
                scheme = data.get("schemes", {}).get(active, {})
                custom = scheme.get("key_codes", {})
            else:
                custom = data.get("key_codes", {})
            if isinstance(custom, dict):
                for k, v in custom.items():
                    if isinstance(k, str) and k.strip() and isinstance(v, int):
                        merged[k.strip().upper()] = v
    except Exception:
        pass
    return merged


def get_custom_commands() -> Dict[str, str]:
    """返回当前激活方案的自定义 adb 命令映射（按键名 → 命令字符串）。

    与 :func:`get_keycode_map` 平行：命令按键走 ``adb <命令>`` 而非 keyevent。
    返回的键名已大写归一。
    """
    commands: Dict[str, str] = {}
    try:
        path = settings.CUSTOMIZATION_FILE
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "schemes" in data:
                active = data.get("active_scheme", "默认")
                scheme = data.get("schemes", {}).get(active, {})
            else:
                scheme = data
            custom = scheme.get("custom_commands", {})
            if isinstance(custom, dict):
                for k, v in custom.items():
                    if isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip():
                        commands[k.strip().upper()] = v
    except Exception:
        pass
    return commands


def _strip_adb_prefix_tokens(command: str) -> List[str]:
    """把用户填写的 adb 命令拆成参数列表，并去掉自带的前缀 ``adb`` 与 ``adb -s <serial>``。

    返回的列表可直接传给 :meth:`ADBController._adb_command`，由它统一补上
    ``adb -s <当前设备>`` 前缀。解析失败（引号不闭合等）返回空列表。

    示例：``adb shell am force-stop com.netflix.ninja`` → ``["shell", "am", ...]``
    """
    try:
        tokens = shlex.split(command.strip())
    except ValueError:
        return []
    if not tokens:
        return []
    if tokens[0].lower() == "adb":
        tokens = tokens[1:]
    if tokens and tokens[0] == "-s" and len(tokens) >= 2:
        tokens = tokens[2:]
    return tokens


def format_timestamped_log(message: str) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"[{timestamp}] {message}"


def console_log(message: str) -> None:
    print(format_timestamped_log(message), flush=True)


def apply_min_command_delay(delay: float) -> float:
    """把命令延迟规整为最终生效的等待时间。

    最终等待 = max(用户给的 delay, ``settings.COMMAND_MIN_DELAY_SECONDS``)
              + ``customization.json::extra_command_delay``

    - ``COMMAND_MIN_DELAY_SECONDS``：兜底硬阈值，默认 0，可在 settings 里启用。
    - ``extra_command_delay``：用户在客制化页面配置的全局额外等待秒数。

    示例：用户写 ``HOME/1/0.5``，extra=1 → 实际等待 1.5 秒；
    用户写 ``HOME/1/2``，extra=1 → 实际等待 3 秒。
    """
    try:
        delay_value = float(delay)
    except (TypeError, ValueError):
        delay_value = 0.0
    if delay_value < 0:
        delay_value = 0.0

    minimum = float(getattr(settings, "COMMAND_MIN_DELAY_SECONDS", 0) or 0)
    if minimum > 0 and delay_value < minimum:
        delay_value = minimum

    extra = _get_extra_command_delay()
    if extra > 0:
        delay_value += extra

    return delay_value


def _get_extra_command_delay() -> float:
    """读取客制化配置里的额外等待秒数（全局 extra_command_delay）。

    直接读 customization.json，避免延迟导入 ``backend.app.api.customization``：
    该模块会连带 import openpyxl，首次调用会卡 ~1.6s，导致命令执行路径上
    的第一条命令被无谓拖慢（也容易让超时类测试变得不确定）。
    """
    try:
        path = settings.CUSTOMIZATION_FILE
        if not path.exists():
            return 0.0
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        try:
            value = float(data.get("extra_command_delay"))
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, value) if value > 0 else 0.0
    except Exception:
        return 0.0


def _parse_key_and_hold(token: str):
    """从 'OK(250000)' 中解析出 ('OK', 250000)，无括号返回 (token, None)。"""
    m = re.match(r'^([A-Za-z0-9_]+)\((\d+)\)$', token.strip())
    if m:
        return m.group(1).upper(), int(m.group(2))
    return token.strip().upper(), None


def _parse_repeat_count(repeat_token: str, wait_time_token: str) -> int:
    """解析指令次数段，支持固定值或随机值 X / X:N / X:(A:B)。

    - 正整数：固定重复次数（保持既有语义，不强制大于 0）。
    - ``X``：随机次数 ∈ [1, int(wait_time_token)]，默认下限 1（保持不变）。
    - ``X:N``：向后兼容写法，等价于 ``X:(1:N)``，随机次数 ∈ [1, N]。
    - ``X:(A:B)``：随机次数 ∈ [A, B]；A、B 均为 0 时固定为 0（该指令本次不执行）。
      随机结果为 0 时同样表示"本次跳过该指令"。

    随机值在每次执行命令时解析一次：同一条指令本次执行内随机次数
    固定，下次执行重新随机。

    Args:
        repeat_token: 次数段原始文本（如 ``3``、``X``、``x:(0:3)``）。
        wait_time_token: 等待时间段原始文本（秒），作为 ``X`` 的随机上限来源。

    Returns:
        本次实际执行的重复次数（可为 0，表示跳过该指令）。

    Raises:
        ValueError: 次数段不符合 正整数 / X / X:N / X:(A:B) 格式，区间 A > B，
            或等待时间无法转 float。
    """
    token = repeat_token.strip().upper()
    if token.isdigit():
        return int(token)

    if token == "X":
        upper = int(float(wait_time_token))
        return random.randint(1, max(1, upper))

    match_range = re.match(r"^X:\((\d+):(\d+)\)$", token)
    if match_range:
        lower = int(match_range.group(1))
        upper = int(match_range.group(2))
        if lower > upper:
            raise ValueError(
                f"随机次数区间 '{repeat_token}' 下限不能大于上限"
            )
        if lower == 0 and upper == 0:
            return 0
        return random.randint(lower, upper)

    # 向后兼容：X:N 等价于 X:(1:N)
    match = re.match(r"^X:(\d+)$", token)
    if match:
        return random.randint(1, max(1, int(match.group(1))))

    raise ValueError(
        f"次数段 '{repeat_token}' 必须为正整数或 X / X:N / X:(A:B)"
    )


def is_valid_repeat_spec(repeat_token: str) -> bool:
    """校验次数段是否合法：正整数、``X``、``X:N`` 或 ``X:(A:B)``（A 下限 ≤ B 上限）。

    纯校验，不产生随机数（与 :func:`_parse_repeat_count` 区分，供 Excel
    上传校验等只读场景使用）。
    """
    token = repeat_token.strip().upper()
    if token.isdigit():
        return int(token) > 0

    if token == "X":
        return True

    match_range = re.match(r"^X:\((\d+):(\d+)\)$", token)
    if match_range:
        return int(match_range.group(1)) <= int(match_range.group(2))

    match = re.match(r"^X:(\d+)$", token)
    return bool(match) and int(match.group(1)) >= 1


def _get_sendevent_device_override() -> Optional[str]:
    """读取客制化配置中的 sendevent 设备路径覆盖值。"""
    try:
        path = settings.CUSTOMIZATION_FILE
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "schemes" in data:
            active = data.get("active_scheme", "默认")
            scheme = data.get("schemes", {}).get(active, {})
        else:
            scheme = data
        device = scheme.get("sendevent_device")
        if isinstance(device, str) and device.strip():
            return device.strip()
    except Exception:
        pass
    return None


def _get_sendevent_keycode_overrides() -> Dict[int, int]:
    """读取客制化配置中的 Android→Linux keycode 覆盖映射。"""
    try:
        path = settings.CUSTOMIZATION_FILE
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "schemes" in data:
            active = data.get("active_scheme", "默认")
            scheme = data.get("schemes", {}).get(active, {})
        else:
            scheme = data
        overrides = scheme.get("sendevent_keycode_overrides", {})
        if isinstance(overrides, dict):
            return {int(k): int(v) for k, v in overrides.items() if k and v is not None}
    except Exception:
        pass
    return {}


def _get_long_press_method() -> str:
    """读取客制化配置中的长按方式：auto / sendevent / input。

    - ``auto``（默认）：先 sendevent，权限不足时尝试 adb root，仍失败回退 input --longpress。
    - ``sendevent``：只用 sendevent，失败即报错（保留原始严格行为）。
    - ``input``：直接走 input keyevent --longpress，不做 sendevent（无需 root）。
    """
    try:
        path = settings.CUSTOMIZATION_FILE
        if not path.exists():
            return "auto"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "schemes" in data:
            active = data.get("active_scheme", "默认")
            scheme = data.get("schemes", {}).get(active, {})
        else:
            scheme = data
        method = str(scheme.get("long_press_method", "auto")).strip().lower()
        if method in ("auto", "sendevent", "input"):
            return method
    except Exception:
        pass
    return "auto"


class ADBController:
    """ADB设备控制器"""

    def __init__(self):
        self.device_serial: Optional[str] = None
        self._stop_event = threading.Event()
        self._execution_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._is_executing = False
        self._recording_process: Optional[subprocess.Popen] = None
        self._recording_remote_path: Optional[str] = None
        # Excel 解析缓存：(文件路径, mtime) -> 解析结果
        self._excel_cache_path: Optional[str] = None
        self._excel_cache_mtime: float = 0.0
        self._excel_cache_result: Optional[Dict[str, Any]] = None
        # 设备长按判定阈值（微秒）缓存，None 表示未查询
        self._long_press_timeout_us: Optional[int] = None

    def _set_executing(self, value: bool) -> None:
        with self._state_lock:
            self._is_executing = value

    def is_executing(self) -> bool:
        with self._state_lock:
            return self._is_executing

    def request_stop(self) -> bool:
        if not self.is_executing():
            return False

        self._stop_event.set()
        return True

    def _should_stop_execution(self) -> bool:
        return self._stop_event.is_set()

    def _wait_with_stop(self, delay: float) -> bool:
        if delay <= 0:
            return True

        deadline = time.perf_counter() + delay
        while True:
            if self._should_stop_execution():
                return False

            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                return True

            time.sleep(min(0.1, remaining))

    @staticmethod
    def _append_stopped_result(results: List[Dict[str, Any]]) -> None:
        if results and results[-1].get("message") == "命令执行已停止":
            return

        results.append({"status": "info", "message": "命令执行已停止"})

    def list_devices(self, timeout: float = 5.0) -> List[str]:
        """列出所有连接的ADB设备。

        通过 ``timeout`` 限定 ``adb devices`` 的最大等待时间，避免 ADB server
        卡住时阻塞调用方（例如 FastAPI 接口）。失败或超时时返回空列表，让上层
        能与"真的没设备"区分（调用方可结合自身状态决定是否保留旧设备）。

        空结果或失败会快速重试一次：ADB server 启动中 / USB 重新枚举等瞬时抖动
        经常让 ``adb devices`` 暂时返回空，若因此清掉用户已选设备会造成"刚选好
        设备又提示没选设备"的诡异现象。
        """
        for attempt in (1, 2):
            devices = self._scan_devices_once(timeout)
            if devices or attempt == 2:
                return devices
            logger.info("[ADB] 首次扫描为空，0.5s 后重试...")
            time.sleep(0.5)
        return []

    def _scan_devices_once(self, timeout: float) -> List[str]:
        logger.info("[ADB] 扫描设备列表 (timeout=%.1fs)", timeout)
        t0 = time.perf_counter()
        try:
            result = subprocess.run(
                "adb devices",
                shell=True,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.error("[ADB] ✗ 扫描设备超时 (耗时=%.0fms, timeout=%.1fs)，可能需要重启 adb server", elapsed_ms, timeout)
            console_log(f"获取设备列表超时（>{timeout}s），可能需要重启 adb server")
            return []
        except subprocess.CalledProcessError as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            stderr = (e.stderr or "").strip()
            logger.error("[ADB] ✗ 扫描设备失败 (耗时=%.0fms): %s | stderr=%s", elapsed_ms, e, stderr)
            console_log(f"获取设备列表失败: {e}")
            return []

        elapsed_ms = (time.perf_counter() - t0) * 1000
        lines = result.stdout.splitlines()
        devices = []
        for line in lines[1:]:
            if line.strip() and "device" in line:
                serial = line.split('\t')[0]
                devices.append(serial)
        logger.info("[ADB] ✓ 扫描完成 (耗时=%.0fms): 发现 %d 个设备 %s", elapsed_ms, len(devices), devices)
        return devices

    def select_device(self, device_serial: str) -> bool:
        """选择要连接的ADB设备"""
        old_serial = self.device_serial
        self.device_serial = device_serial
        logger.info("[ADB] 设备切换: %s -> %s", old_serial or '无', device_serial)
        return True

    def _normalize_excel_text(self, value: Any) -> str:
        if value is None or pd.isna(value):
            return ""
        return str(value).strip()

    def _reconnect_device(self) -> bool:
        """尝试重新连接 ADB 设备。"""
        device_info = self.device_serial or "auto"
        logger.info("[ADB] 🔄 尝试重连设备: %s", device_info)
        try:
            # 先 kill-server 再 start-server，重置 ADB 连接
            subprocess.run(["adb", "kill-server"], capture_output=True, timeout=5)
            time.sleep(1.0)
            subprocess.run(["adb", "start-server"], capture_output=True, timeout=5)
            time.sleep(1.0)
            # 等待设备上线（最多等 10 秒）
            for i in range(5):
                if self.device_serial:
                    result = subprocess.run(
                        ["adb", "-s", self.device_serial, "get-state"],
                        capture_output=True, text=True, timeout=5,
                    )
                    state = (result.stdout or "").strip()
                    if "device" in state:
                        logger.info("[ADB] ✓ 设备重连成功: %s (第 %d 次检测)", device_info, i + 1)
                        return True
                    logger.info("[ADB]   等待设备上线... (state=%s)", state or "无响应")
                time.sleep(2)
        except Exception as e:
            logger.error("[ADB] ✗ 重连失败: %s", e)
        logger.error("[ADB] ✗ 设备重连超时: %s", device_info)
        return False

    def send_keyevent(self, keycode: int, keyname: str, delay: float = 0, max_retries: int = 2) -> bool:
        """发送ADB keyevent并可选延迟，失败时自动重试。"""
        if not 1 <= keycode <= 999:
            raise ValueError("Keycode must be between 1 and 999")

        cmd = self._adb_command("shell", "input", "keyevent", str(keycode))
        device_info = self.device_serial or "auto"

        logger.info("[ADB] ▶ 发送按键: keyname=%s, keycode=%d, device=%s, delay=%.2fs",
                    keyname, keycode, device_info, delay)
        t0 = time.perf_counter()

        for attempt in range(1 + max_retries):
            try:
                result = subprocess.run(cmd, check=True,
                                        capture_output=True, text=True, timeout=10)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.info("[ADB] ✓ 按键成功: keyname=%s, keycode=%d, 耗时=%.0fms, device=%s",
                            keyname, keycode, elapsed_ms, device_info)
                if result.stdout.strip():
                    logger.debug("[ADB]   stdout: %s", result.stdout.strip())
                if delay > 0:
                    logger.info("[ADB]   等待 %.2fs ...", delay)
                    if not self._wait_with_stop(delay):
                        logger.info("[ADB]   收到停止请求，结束 %s 的等待阶段", keyname)
                return True
            except subprocess.CalledProcessError as e:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                stderr_text = (e.stderr or '').strip()
                is_connection_error = "protocol fault" in stderr_text or "connection reset" in stderr_text

                is_device_lost = "not found" in stderr_text
                is_retryable = is_connection_error or is_device_lost

                if is_retryable and attempt < max_retries:
                    logger.warning("[ADB] ⚠ 按键失败(%s)，%d/%d 次重试: keyname=%s, keycode=%d, 耗时=%.0fms",
                                   "连接断开" if is_connection_error else "设备丢失",
                                   attempt + 1, max_retries, keyname, keycode, elapsed_ms)
                    # 尝试重连
                    self._reconnect_device()
                    time.sleep(1.0)
                    continue

                logger.error("[ADB] ✗ 按键失败: keyname=%s, keycode=%d, 耗时=%.0fms, device=%s, returncode=%d, stderr=%s",
                             keyname, keycode, elapsed_ms, device_info, e.returncode, stderr_text)
                console_log(f"发送 {keyname} ({keycode}) 失败: {e}")
                return False
            except subprocess.TimeoutExpired:
                elapsed_ms = (time.perf_counter() - t0) * 1000

                if attempt < max_retries:
                    logger.warning("[ADB] ⚠ 按键超时，%d/%d 次重试: keyname=%s, keycode=%d, 耗时=%.0fms",
                                   attempt + 1, max_retries, keyname, keycode, elapsed_ms)
                    self._reconnect_device()
                    time.sleep(0.5)
                    continue

                logger.error("[ADB] ✗ 按键超时: keyname=%s, keycode=%d, 耗时=%.0fms, device=%s",
                             keyname, keycode, elapsed_ms, device_info)
                return False

    def run_custom_command(self, keyname: str, command: str, delay: float = 0,
                           max_retries: int = 2) -> bool:
        """执行自定义 adb 命令（如 am force-stop 等非 keyevent 操作）。

        用户配置的命令可能带 ``adb`` 前缀，这里经 :func:`_strip_adb_prefix_tokens`
        剥离后交给 ``adb -s <设备>`` 统一执行。连接类错误按 max_retries 重连重试；
        命令返回非零退出码视为"已执行"（记录 warning 并返回成功），避免目标应用
        报错拖垮整条指令序列。

        Args:
            keyname: 自定义命令按键名（仅用于日志）。
            command: 用户填写的 adb 命令原文（可含 ``adb`` 前缀）。
            delay: 命令执行后的额外等待秒数。
            max_retries: 连接类失败重试次数。

        Returns:
            命令是否执行成功（非零退出码视为成功）。
        """
        tokens = _strip_adb_prefix_tokens(command)
        if not tokens:
            logger.error("[ADB] ✗ 自定义命令为空或无法解析: keyname=%s, command=%s", keyname, command)
            return False

        cmd = self._adb_command(*tokens)
        device_info = self.device_serial or "auto"
        logger.info("[ADB] ▶ 自定义命令: keyname=%s, device=%s, cmd=%s", keyname, device_info, " ".join(cmd))
        t0 = time.perf_counter()

        for attempt in range(1 + max_retries):
            try:
                result = subprocess.run(cmd, check=False,
                                        capture_output=True, text=True, timeout=15)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                stderr_text = (result.stderr or "").strip()
                is_connection_error = "protocol fault" in stderr_text or "connection reset" in stderr_text
                is_device_lost = "not found" in stderr_text or "device offline" in stderr_text

                if (is_connection_error or is_device_lost) and attempt < max_retries:
                    logger.warning("[ADB] ⚠ 自定义命令失败(%s)，%d/%d 次重试: keyname=%s, 耗时=%.0fms",
                                   "连接断开" if is_connection_error else "设备丢失",
                                   attempt + 1, max_retries, keyname, elapsed_ms)
                    self._reconnect_device()
                    time.sleep(1.0)
                    continue

                if is_connection_error or is_device_lost:
                    logger.error("[ADB] ✗ 自定义命令失败: keyname=%s, 耗时=%.0fms, stderr=%s",
                                 keyname, elapsed_ms, stderr_text or "(无错误输出)")
                    console_log(f"自定义命令 {keyname} 失败: {stderr_text or '设备连接异常'}")
                    return False

                if result.returncode != 0:
                    # 命令已下发执行（目标应用报错也视为执行完成，仅记录）
                    logger.warning("[ADB] 自定义命令 %s 返回非零退出码 %d: %s",
                                   keyname, result.returncode,
                                   stderr_text[:300] or result.stdout.strip()[:300])
                    console_log(f"自定义命令 {keyname} 执行完成（退出码 {result.returncode}）")
                else:
                    logger.info("[ADB] ✓ 自定义命令成功: keyname=%s, 耗时=%.0fms, device=%s",
                                keyname, elapsed_ms, device_info)
                if result.stdout.strip():
                    logger.debug("[ADB]   stdout: %s", result.stdout.strip()[:500])
                if delay > 0:
                    logger.info("[ADB]   等待 %.2fs ...", delay)
                    if not self._wait_with_stop(delay):
                        logger.info("[ADB]   收到停止请求，结束 %s 的等待阶段", keyname)
                return True
            except subprocess.TimeoutExpired:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                if attempt < max_retries:
                    logger.warning("[ADB] ⚠ 自定义命令超时，%d/%d 次重试: keyname=%s, 耗时=%.0fms",
                                   attempt + 1, max_retries, keyname, elapsed_ms)
                    self._reconnect_device()
                    time.sleep(0.5)
                    continue
                logger.error("[ADB] ✗ 自定义命令超时: keyname=%s, 耗时=%.0fms, device=%s",
                             keyname, elapsed_ms, device_info)
                return False
            except OSError as e:
                logger.error("[ADB] ✗ 自定义命令执行异常: keyname=%s, error=%s", keyname, e)
                return False
        return False

    # ── sendevent 长按 ──────────────────────────────────────────────────────────

    _sendevent_device_cache: Optional[str] = None

    def _detect_sendevent_device(self) -> str:
        """查找含 KEY 能力的 input 设备路径。

        优先读 customization.json 中的 sendevent_device 覆盖值；
        否则通过 ``getevent -pl`` 自动探测；失败回退 /dev/input/event0。
        """
        # 1. 用户手动覆盖
        override = _get_sendevent_device_override()
        if override:
            logger.info("[sendevent] 使用手动配置设备: %s", override)
            return override

        # 2. 缓存
        if self._sendevent_device_cache:
            return self._sendevent_device_cache

        # 3. 自动探测
        try:
            result = subprocess.run(
                self._adb_command("shell", "getevent -pl"),
                capture_output=True, text=True, timeout=10,
            )
            output = result.stdout or ""
            logger.debug("[sendevent] getevent -pl 输出:\n%s", output[:2000])
            current_device = None
            for line in output.splitlines():
                stripped = line.strip()
                if stripped.startswith("add device"):
                    # e.g. "add device 1: /dev/input/event2"
                    parts = stripped.split(":")
                    if len(parts) >= 2:
                        current_device = parts[-1].strip()
                elif current_device and "KEY (" in stripped:
                    # 匹配带标签(-l)或不带标签的输出：
                    #   "KEY (0001): KEY_UP ..." 或 "KEY (0001): { 0067 006c ... }"
                    self._sendevent_device_cache = current_device
                    logger.info("[sendevent] 自动探测到 input 设备: %s", current_device)
                    return current_device
        except Exception as e:
            logger.warning("[sendevent] 自动探测失败: %s", e)

        # 4. 回退
        fallback = "/dev/input/event0"
        logger.info("[sendevent] 回退到默认设备: %s", fallback)
        self._sendevent_device_cache = fallback
        return fallback

    def _get_linux_keycode(self, android_keycode: int) -> int:
        """将 Android keycode 转换为 Linux input-event-codes keycode。"""
        overrides = _get_sendevent_keycode_overrides()
        if android_keycode in overrides:
            return overrides[android_keycode]
        if android_keycode in ANDROID_TO_LINUX_KEYCODE:
            return ANDROID_TO_LINUX_KEYCODE[android_keycode]
        raise ValueError(
            f"Android keycode {android_keycode} 无对应 Linux keycode 映射，"
            f"请在 customization.json 的 sendevent_keycode_overrides 中添加"
        )

    def _get_long_press_timeout_us(self) -> int:
        """查询设备长按判定阈值（毫秒设置，转微秒），结果缓存。失败回退默认值。

        Android InputDispatcher 以 ``settings get secure long_press_timeout``
        （默认 500ms）作为按键长按的判定阈值；低于该值的按住只会被当作普通点按。
        """
        if self._long_press_timeout_us is not None:
            return self._long_press_timeout_us
        try:
            result = subprocess.run(
                self._adb_command("shell", "settings get secure long_press_timeout"),
                capture_output=True, text=True, timeout=10,
            )
            raw = (result.stdout or "").strip()
            ms = int(raw)
            self._long_press_timeout_us = ms * 1000
            logger.info("[sendevent] 设备长按判定阈值: %dms", ms)
        except Exception as e:
            logger.warning("[sendevent] 查询设备长按阈值失败，回退默认 %dms: %s",
                           SENDEVENT_LONG_PRESS_DEFAULT_TIMEOUT_US // 1000, e)
            self._long_press_timeout_us = SENDEVENT_LONG_PRESS_DEFAULT_TIMEOUT_US
        return self._long_press_timeout_us

    def send_long_press(self, keycode: int, keyname: str, hold_us: int,
                        delay: float = 0, max_retries: int = 2) -> bool:
        """按键长按：默认 sendevent，失败自动回退 input keyevent --longpress。

        长按方式 ``long_press_method``（customization.json 中当前方案的配置，
        默认 ``auto``）：

        - ``auto``：先尝试 sendevent（可精确控制按住时长，但写 /dev/input 需要
          root；Android 10+ 非 root 会直接被 SELinux 拒绝）；遇到 Permission
          denied 时尝试 ``adb root`` 提升权限后重试；仍失败则回退
          ``input keyevent --longpress``（经 InputManager 注入，无需 root，
          应用层能识别为长按，但没有真实按住时长）。
        - ``sendevent``：只用 sendevent，失败即报错（保留原始严格行为）。
        - ``input``：直接走 input keyevent --longpress，跳过 sendevent。

        Args:
            keycode: Android keycode。
            keyname: 按键名（用于日志）。
            hold_us: 长按持续时间，单位微秒。
            delay: 松开后的额外等待秒数。
            max_retries: 连接类失败重试次数。
        """
        if hold_us <= 0:
            raise ValueError("hold_us 必须为正整数（微秒）")

        method = _get_long_press_method()
        if method == "input":
            logger.info("[长按] 配置指定 input 方式，跳过 sendevent")
            return self._send_input_long_press(keycode, keyname, delay, max_retries)

        # 长按时长低于设备判定阈值时自动补齐，确保 sendevent 被识别为长按。
        # （input --longpress 是即时注入，不涉及物理时长，无需此逻辑。）
        timeout_us = self._get_long_press_timeout_us()
        if hold_us < timeout_us:
            effective_hold_us = timeout_us + SENDEVENT_LONG_PRESS_MARGIN_US
            logger.warning(
                "[sendevent] 长按 %s: 配置 %dus 低于设备判定阈值 %dus，自动延长至 %dus",
                keyname, hold_us, timeout_us, effective_hold_us)
            console_log(
                f"长按 {keyname}: 配置 {hold_us}us 低于设备判定阈值 {timeout_us}us，"
                f"已自动延长至 {effective_hold_us}us")
            hold_us = effective_hold_us

        if self._try_sendevent_long_press(keycode, keyname, hold_us, delay, max_retries):
            return True

        if method == "sendevent":
            return False

        # auto：回退到无需 root 的 input keyevent --longpress
        logger.warning("[input-longpress] sendevent 长按 %s 失败，回退到 input keyevent --longpress", keyname)
        console_log(f"长按 {keyname}: sendevent 方式不可用，改用 input keyevent --longpress")
        return self._send_input_long_press(keycode, keyname, delay, max_retries)

    def _try_sendevent_long_press(self, keycode: int, keyname: str, hold_us: int,
                                  delay: float, max_retries: int) -> bool:
        """用 sendevent 实现按键长按：按下 → usleep → 松开。

        遇到 ``Permission denied``（非 root / SELinux 拒绝写 /dev/input）时，
        尝试一次 ``adb root`` 提升权限后重试；连接类错误按 max_retries 重连重试。
        """
        try:
            linux_kc = self._get_linux_keycode(keycode)
        except ValueError:
            logger.warning("[sendevent] %s (Android keycode %d) 无 Linux keycode 映射，跳过 sendevent",
                           keyname, keycode)
            return False

        device_info = self.device_serial or "auto"
        t0 = time.perf_counter()
        root_attempted = False

        for attempt in range(1 + max_retries):
            # 每次重试都重新探测设备路径：adb root 重启 adbd 后路径可能变化
            device = self._detect_sendevent_device()
            # 串联为一条 shell 命令减少 adb 连接开销；
            # 用分号分隔确保所有命令都执行（&& 在某些 Android shell 中行为异常）
            shell_cmd = (
                f"sendevent {device} 1 {linux_kc} 1; "
                f"sendevent {device} 0 0 0; "
                f"usleep {hold_us}; "
                f"sendevent {device} 1 {linux_kc} 0; "
                f"sendevent {device} 0 0 0"
            )
            cmd = self._adb_command("shell", shell_cmd)

            logger.info("[sendevent] ▶ 长按: keyname=%s, android_kc=%d, linux_kc=%d, hold=%dus, device=%s, input_dev=%s",
                        keyname, keycode, linux_kc, hold_us, device_info, device)
            logger.info("[sendevent]   shell: %s", shell_cmd)

            try:
                result = subprocess.run(cmd, check=True,
                                        capture_output=True, text=True, timeout=15)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.info("[sendevent] ✓ 长按成功: keyname=%s, hold=%dus, 耗时=%.0fms",
                            keyname, hold_us, elapsed_ms)
                if result.stdout.strip():
                    logger.debug("[sendevent]   stdout: %s", result.stdout.strip())
                if delay > 0:
                    logger.info("[sendevent]   等待 %.2fs ...", delay)
                    if not self._wait_with_stop(delay):
                        logger.info("[sendevent]   收到停止请求，结束 %s 的等待阶段", keyname)
                return True
            except subprocess.CalledProcessError as e:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                stderr_text = (e.stderr or '').strip()

                # 权限不足：尝试一次 adb root 提升权限后再试
                if "Permission denied" in stderr_text and not root_attempted:
                    root_attempted = True
                    logger.warning("[sendevent] ✗ 长按 %s 权限不足 (%s)，尝试 adb root 提升权限",
                                   keyname, stderr_text)
                    console_log(f"sendevent 长按 {keyname} 权限不足，尝试 adb root 提升权限...")
                    if self._try_adb_root():
                        logger.info("[sendevent] adb root 成功，重新探测 input 设备并重试长按 %s", keyname)
                        self._sendevent_device_cache = None  # 强制重新探测设备路径
                        continue
                    logger.warning("[sendevent] adb root 不可用（生产固件或未授权），放弃 sendevent 方式")
                    console_log(f"sendevent 长按 {keyname} 失败: adb root 不可用")
                    return False

                # 连接类错误 → 重连后重试
                is_connection_error = "protocol fault" in stderr_text or "connection reset" in stderr_text
                is_device_lost = "not found" in stderr_text
                if (is_connection_error or is_device_lost) and attempt < max_retries:
                    logger.warning("[sendevent] ⚠ 长按失败(%s)，%d/%d 次重试: keyname=%s",
                                   "连接断开" if is_connection_error else "设备丢失",
                                   attempt + 1, max_retries, keyname)
                    self._reconnect_device()
                    time.sleep(1.0)
                    continue

                logger.error("[sendevent] ✗ 长按失败: keyname=%s, hold=%dus, 耗时=%.0fms, stderr=%s",
                             keyname, hold_us, elapsed_ms, stderr_text)
                console_log(f"sendevent 长按 {keyname} 失败: {e}")
                return False
            except subprocess.TimeoutExpired:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                if attempt < max_retries:
                    logger.warning("[sendevent] ⚠ 长按超时，%d/%d 次重试: keyname=%s",
                                   attempt + 1, max_retries, keyname)
                    self._reconnect_device()
                    time.sleep(0.5)
                    continue
                logger.error("[sendevent] ✗ 长按超时: keyname=%s, hold=%dus, 耗时=%.0fms",
                             keyname, hold_us, elapsed_ms)
                return False
        return False

    def _send_input_long_press(self, keycode: int, keyname: str, delay: float,
                               max_retries: int) -> bool:
        """用 ``input keyevent --longpress`` 实现长按（无需 root）。

        AOSP 7.0+ 的 ``input`` 命令支持 ``--longpress`` 标志：注入带
        ``FLAG_LONG_PRESS`` 的重复事件，InputDispatcher 直接判定为长按并触发
        应用层 ``onKeyLongPress``。注意该方式是即时注入，不会真正按住按键一段
        物理时长；应用能感知到长按，但按住精度低于 sendevent。
        """
        cmd = self._adb_command("shell", "input", "keyevent", "--longpress", str(keycode))
        device_info = self.device_serial or "auto"
        logger.info("[input-longpress] ▶ 长按: keyname=%s, keycode=%d, device=%s",
                    keyname, keycode, device_info)
        t0 = time.perf_counter()

        for attempt in range(1 + max_retries):
            try:
                result = subprocess.run(cmd, check=True,
                                        capture_output=True, text=True, timeout=10)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.info("[input-longpress] ✓ 长按成功: keyname=%s, 耗时=%.0fms", keyname, elapsed_ms)
                if result.stdout.strip():
                    logger.debug("[input-longpress]   stdout: %s", result.stdout.strip())
                if delay > 0:
                    logger.info("[input-longpress]   等待 %.2fs ...", delay)
                    if not self._wait_with_stop(delay):
                        logger.info("[input-longpress]   收到停止请求，结束 %s 的等待阶段", keyname)
                return True
            except subprocess.CalledProcessError as e:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                stderr_text = (e.stderr or '').strip()
                is_connection_error = "protocol fault" in stderr_text or "connection reset" in stderr_text
                is_device_lost = "not found" in stderr_text

                if (is_connection_error or is_device_lost) and attempt < max_retries:
                    logger.warning("[input-longpress] ⚠ 长按失败(%s)，%d/%d 次重试: keyname=%s",
                                   "连接断开" if is_connection_error else "设备丢失",
                                   attempt + 1, max_retries, keyname)
                    self._reconnect_device()
                    time.sleep(1.0)
                    continue

                logger.error("[input-longpress] ✗ 长按失败: keyname=%s, 耗时=%.0fms, stderr=%s",
                             keyname, elapsed_ms, stderr_text)
                console_log(f"input keyevent --longpress 长按 {keyname} 失败: {e}")
                return False
            except subprocess.TimeoutExpired:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                if attempt < max_retries:
                    logger.warning("[input-longpress] ⚠ 长按超时，%d/%d 次重试: keyname=%s",
                                   attempt + 1, max_retries, keyname)
                    self._reconnect_device()
                    time.sleep(0.5)
                    continue
                logger.error("[input-longpress] ✗ 长按超时: keyname=%s, 耗时=%.0fms", keyname, elapsed_ms)
                return False
        return False

    def _try_adb_root(self, wait_timeout: float = 15) -> bool:
        """尝试通过 ``adb root`` 将 adbd 提升为 root。

        仅 userdebug/eng 固件支持；生产固件会返回
        "adbd cannot run as root in production builds" 且不会重启 adbd。
        成功后等待设备重新上线（adbd 重启会短暂 offline）。
        """
        if not self.device_serial:
            return False
        try:
            result = subprocess.run(
                self._adb_command("root"),
                capture_output=True, text=True, timeout=10,
            )
            output = ((result.stdout or "") + (result.stderr or "")).strip()
            logger.info("[sendevent] adb root 输出: %s", output or "(无输出)")
            if "cannot run as root" in output:
                logger.warning("[sendevent] 设备不支持 adb root（生产固件）")
                return False
            if result.returncode != 0:
                logger.warning("[sendevent] adb root 返回码 %d: %s", result.returncode, output)
                return False
            return self._wait_for_device_online(wait_timeout)
        except Exception as e:
            logger.warning("[sendevent] adb root 异常: %s", e)
            return False

    def _wait_for_device_online(self, timeout: float = 15) -> bool:
        """等待 ADB 设备重新上线（adbd 重启后短暂 offline）。"""
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            if self._should_stop_execution():
                return False
            try:
                result = subprocess.run(
                    self._adb_command("get-state"),
                    capture_output=True, text=True, timeout=5,
                )
                if "device" in (result.stdout or "").strip():
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    def execute_commands(self, command_sequence: str) -> List[Dict[str, Any]]:
        """执行多条ADB命令"""
        keycode_map = get_keycode_map()
        custom_commands = get_custom_commands()
        commands = command_sequence.split(',')
        results = []
        logger.info("[ADB] ═══ 批量执行开始: 共 %d 条命令, device=%s ═══",
                    len(commands), self.device_serial or "auto")

        with self._execution_lock:
            self._stop_event.clear()
            self._set_executing(True)

            try:
                for cmd in commands:
                    if self._should_stop_execution():
                        self._append_stopped_result(results)
                        break

                    try:
                        parts = cmd.strip().split('/')
                        if len(parts) != 3:
                            results.append({"status": "error", "message": f"命令格式错误: {cmd}"})
                            continue

                        keyname, hold_us = _parse_key_and_hold(parts[0])
                        repeat = _parse_repeat_count(parts[1], parts[2])
                        delay = apply_min_command_delay(float(parts[2]))

                        if keyname not in keycode_map and keyname not in custom_commands:
                            results.append({"status": "error", "message": f"未知按键: {keyname}"})
                            continue

                        if repeat == 0:
                            # 随机次数为 0：该指令本次不执行（不发送按键、不等待延迟）
                            results.append({"status": "info", "message": f"已跳过 {keyname}（随机次数为 0）"})
                            continue

                        if keyname in NON_EXECUTABLE_KEYS:
                            # ASSERT 等占位按键不发实际 keyevent，但保留指令的延迟语义
                            results.append({"status": "success", "message": f"已跳过非执行按键: {keyname}"})
                            for _ in range(repeat):
                                if self._should_stop_execution():
                                    self._append_stopped_result(results)
                                    return results
                                if not self._wait_with_stop(delay):
                                    self._append_stopped_result(results)
                                    return results
                            continue

                        if keyname in custom_commands:
                            # 自定义 adb 命令按键：执行配置的命令（忽略 hold_us，无长按语义）
                            command = custom_commands[keyname]
                            for _ in range(repeat):
                                if self._should_stop_execution():
                                    self._append_stopped_result(results)
                                    return results

                                success = self.run_custom_command(keyname, command, delay)
                                if success:
                                    results.append({"status": "success", "message": f"已执行自定义命令: {keyname}"})
                                    if self._should_stop_execution():
                                        self._append_stopped_result(results)
                                        return results
                                else:
                                    results.append({"status": "error", "message": f"自定义命令失败: {keyname}"})
                                    break
                            continue

                        keycode = keycode_map[keyname]
                        for _ in range(repeat):
                            if self._should_stop_execution():
                                self._append_stopped_result(results)
                                return results

                            if hold_us is not None:
                                success = self.send_long_press(keycode, keyname, hold_us, delay)
                                label = f"已长按: {keyname} ({hold_us}us)"
                            else:
                                success = self.send_keyevent(keycode, keyname, delay)
                                label = f"已发送: {keyname}"
                            if success:
                                results.append({"status": "success", "message": label})
                                if self._should_stop_execution():
                                    self._append_stopped_result(results)
                                    return results
                            else:
                                results.append({"status": "error", "message": f"发送失败: {keyname}"})
                                break
                    except ValueError as e:
                        results.append({"status": "error", "message": f"命令执行错误: {e}"})

                success_count = sum(1 for r in results if r.get("status") == "success")
                error_count = sum(1 for r in results if r.get("status") == "error")
                logger.info("[ADB] ═══ 批量执行完成: 成功=%d, 失败=%d, 总计=%d ═══",
                            success_count, error_count, len(results))
                return results
            finally:
                self._set_executing(False)
                self._stop_event.clear()

    def _adb_command(self, *args: str) -> List[str]:
        command = ["adb"]
        if self.device_serial:
            command.extend(["-s", self.device_serial])
        command.extend(args)
        return command

    def clear_logcat(self) -> None:
        """清空设备 logcat 缓冲区。"""
        try:
            subprocess.run(
                self._adb_command("logcat", "-c"),
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            pass

    def get_last_tts_text(self, tail_count: int = 200, log_path: Optional[str] = None) -> Optional[str]:
        """从最近的 logcat 输出中提取最后一条 TTS 文本。

        匹配格式: ``tts aric char ="xxx"``（SVOX Pico Engine 等 TTS 引擎输出）

        Args:
            tail_count: 保留参数，暂未使用。
            log_path: 若提供，将过滤后的 logcat 原文保存到该路径。
        """
        try:
            # 设备端过滤，只拉取 TTS 相关日志
            result = subprocess.run(
                self._adb_command("shell", "logcat -d | grep 'tts aric char'"),
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
        except (subprocess.CalledProcessError, OSError, ValueError) as e:
            console_log(f"读取 TTS logcat 失败: {e}")
            return None

        raw_output = result.stdout or ""

        # 保存过滤后的日志到本地文件
        if log_path:
            try:
                from pathlib import Path
                Path(log_path).parent.mkdir(parents=True, exist_ok=True)
                Path(log_path).write_text(raw_output, encoding="utf-8")
            except OSError as e:
                console_log(f"保存 TTS 日志失败: {e}")

        logcat_lines = raw_output.splitlines()

        # 从 "tts aric char = xxx" 行提取 TTS 文本（反向取最后一条）
        # 兼容两种格式: "tts aric char = xxx" 和 "tts aric char ="xxx""
        marker = "tts aric char ="
        for line in reversed(logcat_lines):
            idx = line.find(marker)
            if idx == -1:
                continue
            rest = line[idx + len(marker):]
            # 去掉引号包裹（如果有）
            rest = rest.strip()
            if rest.startswith('"'):
                end = rest.find('"', 1)
                value = rest[1:end].strip() if end != -1 else rest[1:].strip()
            else:
                value = rest.strip()
            if value:
                console_log(f"TTS 输出文本: {value}")
                return value

        # 未匹配到 TTS 标记，拉取完整 logcat 帮助定位问题
        console_log("未捕获到 TTS 输出文本，正在拉取完整 logcat 用于排查...")
        logger.warning("[TTS] 未捕获到 TTS 输出文本，拉取完整 logcat 排查")
        try:
            full_logcat = subprocess.run(
                self._adb_command("logcat", "-d"),
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
            full_lines = (full_logcat.stdout or "").splitlines()
            if full_lines:
                logger.info("[logcat] 录音期间共 %d 行日志:", len(full_lines))
                for line in full_lines:
                    logger.info("[logcat] %s", line)
            else:
                logger.info("[logcat] 录音期间无任何日志输出")
        except Exception as dump_err:
            logger.error("[logcat] 拉取完整日志失败: %s", dump_err)

        return None

    def _remove_local_file(self, file_path) -> None:
        try:
            if file_path.exists():
                file_path.unlink()
        except OSError:
            pass

    def _cleanup_remote_file(self, remote_path: str) -> None:
        try:
            subprocess.run(
                self._adb_command("shell", "rm", remote_path),
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            pass

    def _is_valid_png(self, file_path) -> bool:
        try:
            if not file_path.exists() or file_path.stat().st_size <= 8:
                return False
            with file_path.open("rb") as image_file:
                return image_file.read(8) == b"\x89PNG\r\n\x1a\n"
        except OSError:
            return False

    def _take_screenshot_via_exec_out(self, local_path) -> bool:
        device_info = self.device_serial or "auto"
        logger.info("[ADB] 📷 尝试 exec-out 截图: device=%s, target=%s", device_info, local_path.name)
        t0 = time.perf_counter()
        try:
            with local_path.open("wb") as image_file:
                subprocess.run(
                    self._adb_command("exec-out", "screencap", "-p"),
                    check=True,
                    stdout=image_file,
                    stderr=subprocess.PIPE,
                    timeout=15,
                )
        except subprocess.TimeoutExpired:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            self._remove_local_file(local_path)
            logger.error("[ADB] ✗ exec-out 截图超时: device=%s, 耗时=%.0fms", device_info, elapsed_ms)
            return False
        except (subprocess.CalledProcessError, OSError) as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            self._remove_local_file(local_path)
            logger.error("[ADB] ✗ exec-out 截图失败: device=%s, 耗时=%.0fms, error=%s", device_info, elapsed_ms, e)
            console_log(f"exec-out截图失败: {e}")
            return False

        elapsed_ms = (time.perf_counter() - t0) * 1000
        if self._is_valid_png(local_path):
            file_size = local_path.stat().st_size
            logger.info("[ADB] ✓ exec-out 截图成功: %s (%.1fKB, 耗时=%.0fms)", local_path.name, file_size / 1024, elapsed_ms)
            console_log(f"截图成功，保存到: {local_path}")
            return True

        self._remove_local_file(local_path)
        logger.warning("[ADB] ✗ exec-out 截图失败: 输出不是有效PNG, 耗时=%.0fms", elapsed_ms)
        console_log("exec-out截图失败: 输出不是有效PNG")
        return False

    def _take_screenshot_via_remote_file(self, local_path, file_name: str) -> Optional[str]:
        device_info = self.device_serial or "auto"
        remote_candidates = [
            f"/data/local/tmp/{file_name}",
            f"/sdcard/{file_name}",
        ]
        logger.info("[ADB] 📷 尝试 remote-file 截图: device=%s, file=%s", device_info, file_name)
        t_total = time.perf_counter()

        for remote_path in remote_candidates:
            try:
                t_screencap = time.perf_counter()
                subprocess.run(
                    self._adb_command("shell", "screencap", "-p", remote_path),
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    timeout=15,
                )
                screencap_ms = (time.perf_counter() - t_screencap) * 1000
                logger.info("[ADB]   screencap 完成: remote=%s, 耗时=%.0fms", remote_path, screencap_ms)

                for attempt in range(3):
                    t_pull = time.perf_counter()
                    try:
                        subprocess.run(
                            self._adb_command("pull", remote_path, str(local_path)),
                            check=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            timeout=15,
                        )
                    except subprocess.CalledProcessError as e:
                        pull_ms = (time.perf_counter() - t_pull) * 1000
                        self._remove_local_file(local_path)
                        logger.warning("[ADB]   pull 失败 (尝试 %d/3): remote=%s, 耗时=%.0fms, error=%s",
                                       attempt + 1, remote_path, pull_ms, e)
                        console_log(f"截图拉取失败（尝试 {attempt + 1}/3，{remote_path}）: {e}")
                        time.sleep(0.3)
                        continue
                    except subprocess.TimeoutExpired:
                        pull_ms = (time.perf_counter() - t_pull) * 1000
                        self._remove_local_file(local_path)
                        logger.warning("[ADB]   pull 超时 (尝试 %d/3): remote=%s, 耗时=%.0fms",
                                       attempt + 1, remote_path, pull_ms)
                        time.sleep(0.3)
                        continue

                    pull_ms = (time.perf_counter() - t_pull) * 1000
                    if self._is_valid_png(local_path):
                        file_size = local_path.stat().st_size
                        total_ms = (time.perf_counter() - t_total) * 1000
                        logger.info("[ADB] ✓ remote-file 截图成功: %s (%.1fKB, pull=%.0fms, 总耗时=%.0fms)",
                                    local_path.name, file_size / 1024, pull_ms, total_ms)
                        console_log(f"截图成功，保存到: {local_path}")
                        return str(local_path)

                    self._remove_local_file(local_path)
                    logger.warning("[ADB]   pull 文件无效 (尝试 %d/3): remote=%s", attempt + 1, remote_path)
                    console_log(f"截图文件无效（尝试 {attempt + 1}/3，{remote_path}）")
                    time.sleep(0.3)
            except subprocess.CalledProcessError as e:
                self._remove_local_file(local_path)
                logger.error("[ADB]   screencap 失败: remote=%s, error=%s", remote_path, e)
                console_log(f"截图失败（尝试 {remote_path}）: {e}")
                time.sleep(0.2)
            finally:
                self._cleanup_remote_file(remote_path)

        return None

    def take_screenshot(self, title: Optional[str] = None) -> Optional[str]:
        """使用ADB截图"""
        if title:
            safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)
            file_name = f"{safe_title}.png"
        else:
            ts = int(time.time() * 1000)
            file_name = f"screenshot_{ts}.png"

        local_path = settings.SCREENSHOT_DIR / file_name
        logger.info("[ADB] ═══ 截图开始: title=%s, file=%s ═══", title or '无', file_name)
        t0 = time.perf_counter()

        if self._take_screenshot_via_exec_out(local_path):
            total_ms = (time.perf_counter() - t0) * 1000
            logger.info("[ADB] ═══ 截图完成 (exec-out): 总耗时=%.0fms ═══", total_ms)
            return str(local_path)

        result = self._take_screenshot_via_remote_file(local_path, file_name)
        total_ms = (time.perf_counter() - t0) * 1000
        if result:
            logger.info("[ADB] ═══ 截图完成 (remote-file): 总耗时=%.0fms ═══", total_ms)
        else:
            logger.error("[ADB] ═══ 截图全部失败: 总耗时=%.0fms ═══", total_ms)
        return result

    # ───────────────────── 录屏 ─────────────────────

    def start_recording(self, output_path: str, max_duration: int | None = None) -> bool:
        """启动 ADB screenrecord 录屏。

        Args:
            output_path: 本地输出视频文件路径（.mp4）
            max_duration: 最大录制时长（秒），默认使用 RECORDING_MAX_DURATION

        Returns:
            是否成功启动
        """
        if self._recording_process is not None:
            # 检查旧进程是否已经结束（异常退出未清理）
            poll = self._recording_process.poll()
            if poll is not None:
                logger.warning("[ADB] 发现残留录屏进程 (exit=%s)，自动清理后重新启动", poll)
                self._recording_process = None
                self._recording_remote_path = None
            else:
                logger.warning("[ADB] 录屏进程仍在运行 (pid=%d)，跳过本次启动", self._recording_process.pid)
                return False

        duration = max_duration or int(getattr(settings, "RECORDING_MAX_DURATION", 180))
        ts = int(time.time() * 1000)
        remote_path = f"/data/local/tmp/recording_{ts}.mp4"
        self._recording_remote_path = remote_path

        cmd = self._adb_command("shell", "screenrecord",
                                "--time-limit", str(duration),
                                "--size", "1280x720",
                                remote_path)
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._recording_process = process
            # 短暂等待后确认 screenrecord 在设备端真正启动。
            # 若设备不支持/分辨率不兼容，screenrecord 会立即退出，避免"假启动"导致后续无视频。
            time.sleep(1.0)
            if process.poll() is not None:
                logger.error("[ADB] ✗ screenrecord 启动后立即退出 (exit=%s)，可能设备不支持或分辨率不兼容", process.poll())
                console_log("录屏启动失败：screenrecord 立即退出，请检查设备是否支持录屏")
                self._recording_process = None
                self._recording_remote_path = None
                return False
            logger.info("[ADB] 录屏已启动: remote=%s, pid=%d, duration=%ds",
                        remote_path, process.pid, duration)
            return True
        except Exception as e:
            logger.error("[ADB] 启动录屏失败: %s", e)
            self._recording_remote_path = None
            return False

    def stop_recording(self) -> Optional[str]:
        """停止录屏，拉取视频文件到本地并清理设备临时文件。

        Returns:
            本地视频文件路径，如果没有在录屏则返回 None
        """
        process = self._recording_process
        remote_path = self._recording_remote_path
        if process is None or remote_path is None:
            return None

        self._recording_process = None
        self._recording_remote_path = None

        # 发送 SIGTERM 停止 screenrecord，等它优雅退出并落盘。
        # 录制越久（多段校验）收尾越慢，给足 10s 避免直接 kill 导致 mp4 未收尾损坏。
        try:
            process.terminate()
            process.wait(timeout=10)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

        # 多等一会让 screenrecord 完成文件收尾
        time.sleep(1.0)

        # 拉取文件到本地（失败重试；长录制文件较大，超时给到 60s）
        ts = int(time.time() * 1000)
        local_path = settings.RECORDING_DIR / f"recording_{ts}.mp4"
        for attempt in range(3):
            try:
                result = subprocess.run(
                    self._adb_command("pull", remote_path, str(local_path)),
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            except subprocess.TimeoutExpired:
                self._remove_local_file(local_path)
                logger.warning("[ADB] 拉取录屏超时 (尝试 %d/3): %s", attempt + 1, remote_path)
                time.sleep(1.0)
                continue
            except Exception as e:
                self._remove_local_file(local_path)
                logger.warning("[ADB] 拉取录屏异常 (尝试 %d/3): %s", attempt + 1, e)
                time.sleep(1.0)
                continue

            if result.returncode == 0 and local_path.exists() and local_path.stat().st_size > 0:
                logger.info("[ADB] 录屏文件已拉取: %s", local_path)
                self._cleanup_remote_file(remote_path)
                return str(local_path)

            self._remove_local_file(local_path)
            logger.warning("[ADB] 拉取录屏失败或文件无效 (尝试 %d/3): %s, stderr=%s",
                           attempt + 1, remote_path, (result.stderr or '').strip()[:200])
            time.sleep(1.0)

        # 拉取失败时保留设备端文件，便于排查/重试
        logger.error("[ADB] ✗ 拉取录屏文件失败: %s（已保留设备端文件）", remote_path)
        return None

    @staticmethod
    def _extract_row_commands(valid_rows: list, target_row: Optional[int] = None) -> list:
        """按 1 基索引从有效行中提取目标行的命令列表（与 asr 流一致，不按 Excel 行号查找）。

        兼容两种行格式：SmartTV 模板（含 "commands" 列表）与旧模板（单条 "command" 字符串）。
        """
        if not target_row or not valid_rows:
            return []
        if target_row < 1 or target_row > len(valid_rows):
            return []
        entry = valid_rows[target_row - 1]
        if isinstance(entry, dict) and "commands" in entry:
            return entry.get("commands", [])
        cmd = entry.get("command") if isinstance(entry, dict) else None
        return [cmd] if cmd else []

    def read_excel_commands(self, excel_path: str, target_row: Optional[int] = None) -> Dict[str, Any]:
        """读取Excel文件中的命令（带缓存：同一文件未修改时直接返回）"""
        import os
        try:
            mtime = os.path.getmtime(excel_path)
        except OSError:
            mtime = 0.0

        if (self._excel_cache_result is not None
                and self._excel_cache_path == excel_path
                and self._excel_cache_mtime == mtime):
            result = self._excel_cache_result
            # 只切出目标行的 commands，其余复用缓存（按 valid_rows 的 1 基索引查找）
            if target_row:
                commands = self._extract_row_commands(result.get("valid_rows", []), target_row)
            else:
                commands = result.get("commands", [])
            return {**result, "commands": commands}

        logger.info("[ADB] 读取 Excel: path=%s, target_row=%s", excel_path, target_row or '全部')
        keycode_map = get_keycode_map()
        custom_commands = get_custom_commands()
        valid_keys = {str(key).strip().upper() for key in get_runtime_valid_keys() if str(key).strip()}
        console_log(
            f"[read_excel_commands] ASSERT in keycode_map={'ASSERT' in keycode_map}, "
            f"in valid_keys={'ASSERT' in valid_keys}, "
            f"in NON_EXECUTABLE_KEYS={'ASSERT' in NON_EXECUTABLE_KEYS}"
        )
        try:
            df = pd.read_excel(excel_path)

            commands = []
            valid_rows = []
            skipped_rows = []

            if 'preScript' in df.columns:
                console_log("检测到SmartTV模板格式，正在解析preScript列...")

                all_valid_rows = []
                for index, row in df.iterrows():
                    if 'runOption' in df.columns and str(row['runOption']).upper() != 'Y':
                        skipped_rows.append({"row": index+2, "reason": f"runOption不是Y (值为: {str(row['runOption'])})"})
                        continue

                    ori_step = self._normalize_excel_text(row.get('oriStep', ''))
                    pre_script = self._normalize_excel_text(row.get('preScript', ''))

                    if not ori_step and not pre_script:
                        skipped_rows.append({"row": index+2, "reason": "oriStep和preScript列都为空，用例未识别"})
                        continue

                    combined_commands = []

                    if ori_step:
                        ori_commands = ori_step.split(',')
                        for cmd in ori_commands:
                            cmd = cmd.strip()
                            if not cmd:
                                continue
                            combined_commands.append(cmd)

                    if pre_script:
                        pre_commands = pre_script.split(',')
                        for cmd in pre_commands:
                            cmd = cmd.strip()
                            if not cmd:
                                continue
                            combined_commands.append(cmd)

                    has_valid_command = False
                    missing_mapping_keys = set()
                    invalid_keys = set()
                    malformed_commands = []
                    unparsable_commands = []
                    console_log(
                        f"[read_excel_commands] row={index+2} combined_commands={combined_commands}"
                    )
                    for cmd in combined_commands:
                        try:
                            parts = cmd.split('/')
                            if len(parts) == 3:
                                keyname, _hold_us = _parse_key_and_hold(parts[0])
                                repeat = _parse_repeat_count(parts[1], parts[2])
                                delay = float(parts[2])

                                if keyname in keycode_map or keyname in custom_commands or keyname in NON_EXECUTABLE_KEYS:
                                    # NON_EXECUTABLE_KEYS（如 ASSERT）即使被外部修改/方案
                                    # 覆盖掉 keycode_map，也保证视为有效命令；
                                    # custom_commands（自定义 adb 命令按键）同样视为有效。
                                    has_valid_command = True
                                elif keyname in valid_keys:
                                    missing_mapping_keys.add(keyname)
                                else:
                                    invalid_keys.add(keyname)
                            else:
                                malformed_commands.append(cmd)
                        except ValueError:
                            unparsable_commands.append(cmd)
                    console_log(
                        f"[read_excel_commands] row={index+2} has_valid={has_valid_command} "
                        f"missing={missing_mapping_keys} invalid={invalid_keys} "
                        f"malformed={malformed_commands} unparsable={unparsable_commands}"
                    )

                    if has_valid_command:
                        title = ''
                        step = ''
                        verify_image = ''
                        test_result = ''
                        tts_text = ''

                        if 'testID' in row:
                            title = self._normalize_excel_text(row['testID'])

                        if 'step' in row:
                            step = self._normalize_excel_text(row['step'])
                        elif 'operation' in row:
                            step = self._normalize_excel_text(row['operation'])

                        if 'checkPic' in row:
                            verify_image = self._normalize_excel_text(row['checkPic'])

                        if 'testResult' in row:
                            test_result = self._normalize_excel_text(row['testResult'])

                        # M 列 TTSTXT：用户提供的 TTS 期望文本，供 ASR 比对优先使用
                        if 'TTSTXT' in row:
                            tts_text = self._normalize_excel_text(row['TTSTXT'])

                        all_valid_rows.append({
                            "row": index+2,
                            "title": title,
                            "step": step,
                            "verify_image": verify_image,
                            "test_result": test_result,
                            "tts_text": tts_text,
                            "oriStep": ori_step,
                            "preScript": pre_script,
                            "commands": combined_commands
                        })
                    else:
                        if missing_mapping_keys:
                            reason = f"按键缺少键值映射: {', '.join(sorted(missing_mapping_keys))}"
                        elif invalid_keys:
                            reason = f"存在未识别按键: {', '.join(sorted(invalid_keys))}"
                        elif malformed_commands:
                            reason = f"存在格式错误命令: {', '.join(malformed_commands)}"
                        elif unparsable_commands:
                            reason = f"存在无法解析的命令参数: {', '.join(unparsable_commands)}"
                        else:
                            reason = "oriStep和preScript列中没有有效命令"
                        skipped_rows.append({"row": index+2, "reason": reason})

                valid_rows = all_valid_rows
                console_log(f"处理完成：总有效行 {len(valid_rows)} 个")
            else:
                required_columns = ['keyname', 'repeat', 'delay']
                for col in required_columns:
                    if col not in df.columns:
                        raise ValueError(f"Excel文件缺少必要的列: {col}")

                for index, row in df.iterrows():
                    try:
                        keyname = str(row.get('keyname', '')).upper()
                        if not keyname:
                            skipped_rows.append({"row": index+2, "reason": "keyname列为空"})
                            continue

                        repeat = int(row.get('repeat', 0))
                        if repeat <= 0:
                            skipped_rows.append({"row": index+2, "reason": "repeat值必须大于0"})
                            continue

                        delay = float(row.get('delay', 0))
                        if delay < 0:
                            skipped_rows.append({"row": index+2, "reason": "delay值不能小于0"})
                            continue

                        if keyname not in keycode_map and keyname not in custom_commands:
                            if keyname in valid_keys:
                                skipped_rows.append({"row": index+2, "reason": f"keyname '{keyname}' 缺少键值映射"})
                            else:
                                skipped_rows.append({"row": index+2, "reason": f"keyname '{keyname}' 不存在于按键映射表中"})
                            continue

                        cmd_str = f"{keyname}/{repeat}/{delay}"
                        valid_rows.append({"row": index+2, "command": cmd_str})
                    except (ValueError, TypeError) as e:
                        skipped_rows.append({"row": index+2, "reason": f"数据类型错误: {str(e)}"})

            commands = self._extract_row_commands(valid_rows, target_row)

            logger.info("[ADB] Excel 解析完成: 有效行=%d, 跳过=%d, 目标行命令数=%d",
                        len(valid_rows), len(skipped_rows), len(commands))
            if skipped_rows:
                for sr in skipped_rows[:5]:
                    logger.debug("[ADB]   跳过行 %s: %s", sr.get('row'), sr.get('reason'))
                if len(skipped_rows) > 5:
                    logger.debug("[ADB]   ... 还有 %d 行被跳过", len(skipped_rows) - 5)
            result = {
                "commands": commands,
                "valid_rows": valid_rows,
                "skipped_rows": skipped_rows,
                "total_rows": len(valid_rows)
            }
            # 写入缓存
            self._excel_cache_path = excel_path
            self._excel_cache_mtime = mtime
            self._excel_cache_result = result
            return result
        except Exception as e:
            logger.error("[ADB] ✗ Excel 读取失败: %s", e)
            raise Exception(f"读取Excel失败: {e}")
