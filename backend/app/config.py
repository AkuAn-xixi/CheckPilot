"""应用配置模块"""
import sys
from pathlib import Path


def _get_bundle_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def _get_runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


class Settings:
    """应用配置类"""

    PROJECT_NAME: str = "AutoDeck API"
    VERSION: str = "1.1.1"
    DESCRIPTION: str = "AutoDeck 自动测控台：ADB设备控制、Excel测试执行与结果校验API"

    CORS_ORIGINS: list = ["*"]
    BUNDLE_DIR: Path = _get_bundle_dir()
    WORKING_DIR: Path = _get_runtime_dir()
    SCREENSHOT_DIR: Path = WORKING_DIR / "screenshots"
    TEST_CASES_DIR: Path = WORKING_DIR / "test_cases"
    ASR_MODELS_DIR: Path = WORKING_DIR / "asr_models"
    REPORTS_DIR: Path = WORKING_DIR / "reports"
    RECORDING_DIR: Path = WORKING_DIR / "recordings"
    LOG_DIR: Path = WORKING_DIR / "log"
    CAPTURE_CARD_DEVICE_ID: int = 1
    CAPTURE_CARD_WIDTH: int = 1920
    CAPTURE_CARD_HEIGHT: int = 1080
    CAPTURE_CARD_FPS_TARGET: int = 60
    # MJPEG 通常能让 USB 采集卡稳定跑 1080p60；YUY2 在 USB2 带宽下大多被限到 30fps。
    # 设为 "" 表示沿用驱动默认。常见可选: "MJPG" / "YUY2" / "NV12"
    CAPTURE_CARD_FOURCC: str = "MJPG"
    # 后端推流目标帧率：0 表示不主动节流，由采集 + 编码自然吃满
    CAPTURE_CARD_STREAM_FPS: int = 60
    # MJPEG 编码质量 0-100；75 在视觉上和 90+ 几乎不可分辨，但帧时间能少一半
    CAPTURE_CARD_JPEG_QUALITY: int = 75
    CAPTURE_CARD_RECORDING_FPS: int = 30
    RECORDING_MAX_DURATION: int = 180

    # scrcpy 串流配置
    SCRCPY_ENABLED: bool = True
    SCRCPY_PATH: str = "scrcpy"  # scrcpy 可执行文件路径，PATH 中有则直接填 "scrcpy"
    SCRCPY_MAX_SIZE: int = 1024  # 串流分辨率上限（长边像素）
    SCRCPY_MAX_FPS: int = 30  # 串流帧率上限
    SCRCPY_VIDEO_CODEC: str = "h264"  # 编码格式：h264 / h265
    SCRCPY_NO_AUDIO: bool = True
    SCRCPY_JPEG_QUALITY: int = 80  # MJPEG 转码质量 1-31（FFmpeg 标准，越小质量越高）
    SCRCPY_IDLE_TIMEOUT: float = 10.0  # 无人消费后自动释放 scrcpy 进程的秒数
    FFMPEG_PATH: str = "ffmpeg"  # FFmpeg 可执行文件路径
    ADB_TIMEOUT: int = 30
    CUSTOMIZATION_FILE: Path = WORKING_DIR / "customization.json"

    # 命令执行的硬最小延迟（秒）。0 表示不强制最低值。早期版本默认 1 秒避免
     # 连按过快，现在改为由用户在客制化页配置 ``extra_command_delay`` 来叠加额外
    # 等待时间，更直观；保留这个 settings 项以备需要时启用。
    COMMAND_MIN_DELAY_SECONDS: float = 0.0

    @property
    def FRONTEND_DIST_DIR(self) -> Path:
        candidates = [
            self.WORKING_DIR / "frontend" / "dist",
            self.BUNDLE_DIR / "frontend" / "dist",
            self.WORKING_DIR / "dist_frontend",
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                return candidate
        return self.BUNDLE_DIR / "frontend" / "dist"

    def ensure_runtime_dirs(self) -> None:
        self.WORKING_DIR.mkdir(parents=True, exist_ok=True)
        self.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        self.ASR_MODELS_DIR.mkdir(parents=True, exist_ok=True)
        self.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        self.RECORDING_DIR.mkdir(parents=True, exist_ok=True)
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)
        (self.TEST_CASES_DIR / "excel").mkdir(parents=True, exist_ok=True)
        (self.TEST_CASES_DIR / "images").mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_runtime_dirs()
