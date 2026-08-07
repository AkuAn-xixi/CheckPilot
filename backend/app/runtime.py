"""运行时状态访问工具。"""
import json
import logging
import sys
from types import ModuleType
from typing import Any, List, Optional

from .config import settings
from .utils.adb_controller import ADBController

logger = logging.getLogger(__name__)


RUNTIME_STATE_FILE = settings.WORKING_DIR / "runtime_state.json"


class _RuntimeState:
    def __init__(self):
        self.controller = ADBController()
        self.current_device: Optional[str] = None
        self.monitor_live_sequence: str = ""
        self.platform_auth: dict[str, Any] = {}


runtime_state = _RuntimeState()


def _read_persisted_runtime_state() -> dict:
    if not RUNTIME_STATE_FILE.exists():
        return {}

    try:
        return json.loads(RUNTIME_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_persisted_runtime_state(data: dict) -> None:
    if not data:
        try:
            if RUNTIME_STATE_FILE.exists():
                RUNTIME_STATE_FILE.unlink()
        except OSError:
            pass
        return

    RUNTIME_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _persist_current_device(device_serial: Optional[str]) -> None:
    state = _read_persisted_runtime_state()
    if device_serial:
        state["current_device"] = device_serial
    else:
        state.pop("current_device", None)
    _write_persisted_runtime_state(state)


def _restore_current_device_from_disk() -> None:
    if runtime_state.current_device:
        return

    state = _read_persisted_runtime_state()
    persisted_device = state.get("current_device")
    if persisted_device:
        runtime_state.current_device = persisted_device


def _persist_platform_auth(platform_auth: Optional[dict[str, Any]]) -> None:
    state = _read_persisted_runtime_state()
    if platform_auth:
        state["platform_auth"] = platform_auth
    else:
        state.pop("platform_auth", None)
    _write_persisted_runtime_state(state)


def _restore_platform_auth_from_disk() -> None:
    if runtime_state.platform_auth:
        return

    state = _read_persisted_runtime_state()
    platform_auth = state.get("platform_auth")
    if isinstance(platform_auth, dict):
        runtime_state.platform_auth = platform_auth


def get_platform_auth() -> dict[str, Any]:
    _restore_platform_auth_from_disk()
    return dict(runtime_state.platform_auth)


def set_platform_auth(platform_auth: dict[str, Any]) -> None:
    normalized = dict(platform_auth or {})
    runtime_state.platform_auth = normalized
    _persist_platform_auth(normalized)


def clear_platform_auth() -> None:
    runtime_state.platform_auth = {}
    _persist_platform_auth(None)


def _persist_capture_card_device(device: Optional[dict[str, Any]]) -> None:
    state = _read_persisted_runtime_state()
    if device:
        state["capture_card_device"] = device
    else:
        state.pop("capture_card_device", None)
    _write_persisted_runtime_state(state)


def get_capture_card_device() -> dict[str, Any]:
    state = _read_persisted_runtime_state()
    device = state.get("capture_card_device")
    if isinstance(device, dict):
        return dict(device)
    return {}


def set_capture_card_device(device: dict[str, Any]) -> None:
    if not isinstance(device, dict):
        raise ValueError("capture card device must be a dict")
    normalized = {
        "device_id": int(device.get("device_id", 0)),
        "label": str(device.get("label", "") or ""),
    }
    _persist_capture_card_device(normalized)


def _get_main_module() -> Optional[ModuleType]:
    for module_name in ("backend.main", "main"):
        module = sys.modules.get(module_name)
        if module is not None:
            return module
    return None


def get_controller() -> ADBController:
    module = _get_main_module()
    controller = getattr(module, "controller", None) if module is not None else None

    if controller is None:
        controller = runtime_state.controller
        if module is not None:
            module.controller = controller
    else:
        runtime_state.controller = controller

    return controller


def get_current_device() -> Optional[str]:
    """返回上次选中的设备序列号，仅读取持久化状态。

    早期实现会顺带调用 ``adb devices`` 做在线检测，并在掉线时主动清空当前设备。
    但 ``/api/devices/current`` 几乎被每个页面在挂载时调用，一旦 ADB server 抖
    动（例如 USB 重新枚举、其他工具占用），调用就会被错误地解释为"设备已离
    线"，从而把用户已选的设备从持久化文件中抹除。

    这里把"在线检测"职责交给 :func:`prune_current_device_if_offline`，由
    ``/api/devices/list`` 等会显式拉取设备列表的接口在用户主动刷新时调用。
    """

    module = _get_main_module()
    module_device = getattr(module, "current_device", None) if module is not None else None
    if module_device:
        runtime_state.current_device = module_device
    else:
        # 模块全局 current_device 为空（可能被某些路径重置）时，回退到磁盘持久化值，
        # 避免把用户已选设备误清空。
        _restore_current_device_from_disk()

    current_device = runtime_state.current_device
    if not current_device:
        return None

    controller = get_controller()
    if controller.device_serial != current_device:
        controller.select_device(current_device)

    if module is not None and getattr(module, "current_device", None) != current_device:
        module.current_device = current_device
        module.controller = controller

    return current_device


def prune_current_device_if_offline(available_devices: List[str]) -> Optional[str]:
    """根据传入的在线设备列表，决定是否清理当前选中设备。

    返回当前生效的设备序列号；若已被清理则返回 ``None``。供 ``/api/devices/list``
    在用户主动刷新设备时使用，避免在每次只读"当前设备"接口里做检测。

    特殊兜底：``available_devices`` 为空列表时，**不**清理已选设备。空列表大多
    数情况下意味着 ``adb devices`` 临时返回失败（ADB server 启动中、USB 重新
    枚举、或者 ``adb devices`` 命令本身超时），如果这时清理就会出现"刚选好
    设备，进 Excel 执行又被提示没选设备"的诡异现象。真正的"设备掉线"会表
    现为"列表里有别的设备但缺刚选的那一台"，那个分支才走清理逻辑。
    """

    current_device = get_current_device()
    if not current_device:
        return None

    # 空列表多半是 adb 暂时不可用，保持现有选择不变
    if not available_devices:
        return current_device

    if current_device in available_devices:
        _persist_current_device(current_device)
        return current_device

    logger.warning(
        "[设备] 当前设备 %s 不在在线设备列表 %s 中，判定为掉线并清空选择",
        current_device,
        available_devices,
    )
    runtime_state.current_device = None
    controller = get_controller()
    controller.device_serial = None
    _persist_current_device(None)

    module = _get_main_module()
    if module is not None:
        module.current_device = None
        module.controller = controller

    return None


def set_current_device(device_serial: str) -> None:
    runtime_state.current_device = device_serial
    _persist_current_device(device_serial)

    controller = get_controller()
    controller.select_device(device_serial)

    module = _get_main_module()
    if module is not None:
        module.current_device = device_serial
        module.controller = controller


def get_monitor_live_sequence() -> str:
    module = _get_main_module()
    if module is not None and hasattr(module, "monitor_live_sequence"):
        runtime_state.monitor_live_sequence = module.monitor_live_sequence
    return runtime_state.monitor_live_sequence