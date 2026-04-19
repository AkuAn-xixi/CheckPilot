"""应用配置模块"""
import os

class Settings:
    """应用配置类"""
    PROJECT_NAME: str = "ADB Control API"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "ADB设备控制和命令执行API"

    # CORS配置
    CORS_ORIGINS: list = ["*"]

    # 工作目录
    WORKING_DIR: str = os.getcwd()

    # 截图保存目录
    SCREENSHOT_DIR: str = os.getcwd()

    # ADB配置
    ADB_TIMEOUT: int = 30

settings = Settings()
