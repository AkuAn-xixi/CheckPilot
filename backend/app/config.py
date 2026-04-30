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

    PROJECT_NAME: str = "ADB Control API"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "ADB设备控制和命令执行API"

    CORS_ORIGINS: list = ["*"]
    BUNDLE_DIR: Path = _get_bundle_dir()
    WORKING_DIR: Path = _get_runtime_dir()
    SCREENSHOT_DIR: Path = WORKING_DIR / "screenshots"
    TEST_CASES_DIR: Path = WORKING_DIR / "test_cases"
    ASR_MODELS_DIR: Path = WORKING_DIR / "asr_models"
    ADB_TIMEOUT: int = 30
    CUSTOMIZATION_FILE: Path = WORKING_DIR / "customization.json"

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
        (self.TEST_CASES_DIR / "excel").mkdir(parents=True, exist_ok=True)
        (self.TEST_CASES_DIR / "images").mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_runtime_dirs()
