"""服务模块"""
from .asr_service import asr_service
from .device_service import device_service
from .excel_service import excel_service
from .image_service import image_verifier, verify_image_match

__all__ = ["asr_service", "device_service", "excel_service", "image_verifier", "verify_image_match"]
