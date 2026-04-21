"""运行时状态访问工具。"""
import sys
from types import ModuleType
from typing import Optional

from app.utils.adb_controller import ADBController


class _RuntimeState:
    def __init__(self):
        self.controller = ADBController()
        self.current_device: Optional[str] = None
        self.monitor_live_sequence: str = ""


runtime_state = _RuntimeState()


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

    current_device = runtime_state.current_device
    if current_device:
        controller = get_controller()
        if controller.device_serial != current_device:
            controller.select_device(current_device)

    return current_device


def set_current_device(device_serial: str) -> None:
    runtime_state.current_device = device_serial

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