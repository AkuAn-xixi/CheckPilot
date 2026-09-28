"""按键捕获的 HTTP 接口。

只做「解析参数 → 调用 service → 格式化输出」。捕获结果的落盘不在这里，
由前端走既有的 key-codes / sendevent-config / keymonitor-mappings 接口完成，
这样后端不新增写路径，也不会跨模块去碰别人的存储文件。
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from ..runtime import get_controller
from ..services.key_capture_service import KeyCaptureError, KeyCaptureService

router = APIRouter(prefix="/api/key-capture", tags=["key-capture"])

# 会话是进程级的，这里只放一个实例。放在 api 层而不是 runtime.py 是为了断开
# runtime → services/__init__ → device_service → runtime 的循环导入。
_capture_service: Optional[KeyCaptureService] = None


def get_key_capture_service() -> KeyCaptureService:
    """返回全局唯一的捕获服务。

    持的是 :func:`get_controller` 那一个 ``ADBController``，不自己新建，
    这样用户在设备列表里切换设备后捕获会自动跟着走。
    """
    global _capture_service
    if _capture_service is None:
        _capture_service = KeyCaptureService(get_controller())
    return _capture_service


@router.post("/start")
def start_capture() -> Dict[str, Any]:
    """开始一次捕获会话。

    Raises:
        HTTPException: 已有会话在进行，或读取设备状态失败（400）。
    """
    service = get_key_capture_service()
    try:
        service.start()
    except KeyCaptureError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"success": True, **service.status()}


@router.post("/stop")
def stop_capture() -> Dict[str, Any]:
    """结束捕获会话。幂等：没有进行中的会话时直接返回当前状态。"""
    service = get_key_capture_service()
    service.stop()
    return {"success": True, **service.status()}


@router.get("/status")
def get_capture_status() -> Dict[str, Any]:
    """查询会话是否在跑、已捕获多少条、以及来源设备清单。"""
    return get_key_capture_service().status()


@router.get("/events")
def list_capture_events(since: int = Query(0, ge=0)) -> Dict[str, Any]:
    """增量拉取捕获结果。

    Args:
        since: 前端上次拿到的最大序号，首次传 0。
    """
    return get_key_capture_service().list_events(since)
