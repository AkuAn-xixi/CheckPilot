"""API路由模块"""
from .auth import router as auth_router
from .asr import router as asr_router
from .customization import router as customization_router
from .devices import router as devices_router
from .excel import router as excel_router
from .execution import router as execution_router
from .reports import router as reports_router

__all__ = ["auth_router", "asr_router", "customization_router", "devices_router", "excel_router", "execution_router", "reports_router"]
