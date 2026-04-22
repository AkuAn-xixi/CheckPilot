"""设备服务模块"""
from typing import List, Optional
from ..runtime import get_controller

class DeviceService:
    """设备服务类"""

    def __init__(self):
        self.controller = get_controller()

    def get_devices(self) -> List[str]:
        """获取设备列表"""
        self.controller = get_controller()
        return self.controller.list_devices()

    def select_device(self, device_serial: str) -> bool:
        """选择设备"""
        self.controller = get_controller()
        return self.controller.select_device(device_serial)

device_service = DeviceService()
