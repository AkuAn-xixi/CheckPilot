"""设备服务模块"""
from typing import List, Optional
from app.utils.adb_controller import ADBController

class DeviceService:
    """设备服务类"""

    def __init__(self):
        self.controller = ADBController()

    def get_devices(self) -> List[str]:
        """获取设备列表"""
        return self.controller.list_devices()

    def select_device(self, device_serial: str) -> bool:
        """选择设备"""
        return self.controller.select_device(device_serial)

device_service = DeviceService()
