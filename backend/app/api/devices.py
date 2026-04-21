"""设备API路由模块"""
from fastapi import APIRouter, HTTPException
from app.models.schemas import DeviceSelectRequest, CommandExecuteRequest, SingleCommandExecuteRequest
from app.runtime import get_controller, get_current_device as get_current_device_state, set_current_device
from app.services.device_service import device_service
from app.utils.adb_controller import KEYCODE_MAP

router = APIRouter(prefix="/api/devices", tags=["devices"])

@router.get("/list")
async def list_devices():
    """获取设备列表"""
    devices = device_service.get_devices()
    return {"devices": devices, "count": len(devices)}

@router.post("/select")
async def select_device(request: DeviceSelectRequest):
    """选择设备"""
    devices = device_service.get_devices()
    if not devices:
        raise HTTPException(status_code=400, detail="没有找到已连接的设备")

    try:
        index = int(request.device_index)
        if index < 0 or index >= len(devices):
            raise HTTPException(status_code=400, detail=f"设备索引无效，有效范围: 0-{len(devices)-1}")

        device_serial = devices[index]
        set_current_device(device_serial)
        return {"status": "success", "device": device_serial}
    except ValueError:
        raise HTTPException(status_code=400, detail="设备索引必须是整数")

@router.get("/current")
async def get_current_device():
    """获取当前连接的设备"""
    return {"device": get_current_device_state()}

@router.post("/commands/execute")
async def execute_commands(request: CommandExecuteRequest):
    """执行命令序列"""
    current_device = get_current_device_state()
    if not current_device:
        raise HTTPException(status_code=400, detail="请先选择设备")

    controller = get_controller()
    results = controller.execute_commands(request.commands)
    return {"results": results}

@router.post("/execute")
async def execute_single_command(request: SingleCommandExecuteRequest):
    """执行单个命令"""
    current_device = get_current_device_state()
    if not current_device:
        raise HTTPException(status_code=400, detail="请先选择设备")

    command = request.command
    if not command:
        raise HTTPException(status_code=400, detail="请提供命令")

    controller = get_controller()
    execution_results = controller.execute_commands(command)
    return {
        "execution_results": execution_results,
        "executed_command": command
    }
