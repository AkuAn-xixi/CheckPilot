"""运行时状态访问工具。"""
import json
import sys
from types import ModuleType
from typing import Optional

from .config import settings
from .utils.adb_controller import ADBController


RUNTIME_STATE_FILE = settings.WORKING_DIR / "runtime_state.json"


class _RuntimeState:
    def __init__(self):
        self.controller = ADBController()
        self.current_device: Optional[str] = None
        self.monitor_live_sequence: str = ""


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
    module = _get_main_module()
    if module is not None and hasattr(module, "current_device"):
        runtime_state.current_device = module.current_device
    else:
        _restore_current_device_from_disk()

    current_device = runtime_state.current_device
    if current_device:
        controller = get_controller()
        available_devices = controller.list_devices()
        if current_device not in available_devices:
            runtime_state.current_device = None
            controller.device_serial = None
            _persist_current_device(None)
            if module is not None:
                module.current_device = None
                module.controller = controller
            return None

        if controller.device_serial != current_device:
            controller.select_device(current_device)

        _persist_current_device(current_device)

    return current_device


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