"""API路由模块"""
from .devices import router as devices_router
from .excel import router as excel_router
from .execution import router as execution_router

__all__ = ["devices_router", "excel_router", "execution_router"]
