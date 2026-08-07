"""设备API路由模块"""
import asyncio
import base64
import binascii
import os
import time
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from ..config import settings
from ..models.schemas import CaptureCardDeviceSelectRequest, DevicePreviewSaveRequest, DeviceSelectRequest, CommandExecuteRequest, SingleCommandExecuteRequest
from ..runtime import get_controller, get_current_device as get_current_device_state, prune_current_device_if_offline, set_current_device
from ..services.capture_card_service import capture_card_service
from ..services.device_service import device_service
from ..services.scrcpy_service import scrcpy_service
from ..utils.adb_controller import KEYCODE_MAP
from ..utils.path_resolver import get_image_dir

router = APIRouter(prefix="/api/devices", tags=["devices"])
PREVIEW_SOURCE_ADB = "adb"
PREVIEW_SOURCE_CAPTURE_CARD = "capture_card"
PREVIEW_SOURCE_SCRCPY = "scrcpy"
PREVIEW_STREAM_BOUNDARY = b"frame"


def _sanitize_preview_file_stem(value: str) -> str:
    sanitized = ''.join('_' if char in '\\/:*?"<>|' else char for char in str(value or '').strip())
    sanitized = sanitized.strip().strip('.')
    return sanitized or 'screenshot'


def _resolve_preview_save_dir(save_dir: str | None) -> Path:
    normalized = str(save_dir or '').strip()
    if not normalized:
        return get_image_dir().resolve(strict=False)

    candidate = Path(os.path.expandvars(normalized)).expanduser()
    if not candidate.is_absolute():
        candidate = settings.WORKING_DIR / candidate
    return candidate.resolve(strict=False)


def _build_unique_preview_file_name(save_dir: Path, requested_file_name: str | None) -> str:
    requested_path = Path(str(requested_file_name or '').strip())
    suffix = requested_path.suffix.lower() or '.png'
    if suffix != '.png':
        suffix = '.png'

    stem_source = requested_path.stem or requested_path.name or 'screenshot'
    base_stem = _sanitize_preview_file_stem(stem_source)
    candidate_name = f"{base_stem}{suffix}"
    if not (save_dir / candidate_name).exists():
        return candidate_name

    index = 1
    while True:
        candidate_name = f"{base_stem}-{index}{suffix}"
        if not (save_dir / candidate_name).exists():
            return candidate_name
        index += 1


def _build_preview_overwrite_file_name(requested_file_name: str | None) -> str:
    """与 ``_build_unique_preview_file_name`` 类似，但忽略文件冲突，直接返回归一后名字。"""
    requested_path = Path(str(requested_file_name or '').strip())
    suffix = requested_path.suffix.lower() or '.png'
    if suffix != '.png':
        suffix = '.png'

    stem_source = requested_path.stem or requested_path.name or 'screenshot'
    base_stem = _sanitize_preview_file_stem(stem_source)
    return f"{base_stem}{suffix}"


def _build_preview_image_reference(saved_path: Path) -> str:
    default_image_dir = get_image_dir().resolve(strict=False)
    if saved_path.parent.resolve(strict=False) == default_image_dir:
        return saved_path.name
    return str(saved_path)


def _normalize_preview_source(source: str | None) -> str:
    normalized = str(source or PREVIEW_SOURCE_ADB).strip().lower()
    if normalized not in {PREVIEW_SOURCE_ADB, PREVIEW_SOURCE_CAPTURE_CARD, PREVIEW_SOURCE_SCRCPY}:
        raise HTTPException(status_code=400, detail="预览来源无效")
    return normalized


def _build_mjpeg_frame_chunk(image_bytes: bytes) -> bytes:
    return (
        b"--" + PREVIEW_STREAM_BOUNDARY + b"\r\n"
        + b"Content-Type: image/jpeg\r\n"
        + f"Content-Length: {len(image_bytes)}\r\n\r\n".encode("ascii")
        + image_bytes
        + b"\r\n"
    )


def _iter_capture_card_preview_stream(first_frame: dict):
    target_fps = int(getattr(settings, "CAPTURE_CARD_STREAM_FPS", 0) or 0)
    frame_interval = (1.0 / target_fps) if target_fps > 0 else 0.0
    next_frame_deadline = time.perf_counter()

    yield _build_mjpeg_frame_chunk(first_frame["bytes"])
    last_frame_at = time.perf_counter()

    while True:
        try:
            jpeg_bytes, frame_perf, _meta = capture_card_service.wait_for_new_jpeg(
                last_frame_at,
                timeout=1.0,
            )
        except RuntimeError:
            break

        yield _build_mjpeg_frame_chunk(jpeg_bytes)
        last_frame_at = frame_perf

        if frame_interval > 0:
            next_frame_deadline += frame_interval
            sleep_duration = next_frame_deadline - time.perf_counter()
            if sleep_duration > 0:
                time.sleep(sleep_duration)
            else:
                next_frame_deadline = time.perf_counter()


def _iter_scrcpy_preview_stream(first_frame: dict):
    """scrcpy 的 MJPEG 流生成器，与采集卡流结构一致。"""
    yield _build_mjpeg_frame_chunk(first_frame["bytes"])
    last_frame_at = time.perf_counter()

    while True:
        try:
            jpeg_bytes, frame_perf, _meta = scrcpy_service.wait_for_new_jpeg(
                last_frame_at,
                timeout=1.0,
            )
        except RuntimeError:
            break

        yield _build_mjpeg_frame_chunk(jpeg_bytes)
        last_frame_at = frame_perf

@router.get("/list")
async def list_devices():
    """获取设备列表"""
    # device_service.get_devices() 内部会执行 ``adb devices``，是阻塞 IO。
    # 用 to_thread 把它扔到线程池，避免 ADB server 抖动时把整个事件循环卡死，
    # 进而导致后续 /api/devices/current 等请求排队"一直加载中"。
    devices = await asyncio.to_thread(device_service.get_devices)
    prune_current_device_if_offline(devices)
    return {"devices": devices, "count": len(devices)}

@router.post("/select")
async def select_device(request: DeviceSelectRequest):
    """选择设备"""
    devices = await asyncio.to_thread(device_service.get_devices)
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


@router.get("/preview")
async def get_device_preview(source: Annotated[str, Query(description="预览来源: adb / capture_card / scrcpy")] = PREVIEW_SOURCE_ADB):
    """获取当前设备或采集卡或 scrcpy 的最新预览截图。"""
    preview_source = _normalize_preview_source(source)

    if preview_source == PREVIEW_SOURCE_SCRCPY:
        current_device = get_current_device_state()
        if not current_device:
            raise HTTPException(status_code=400, detail="请先选择设备")
        try:
            result = scrcpy_service.capture_encoded_frame()
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        return {
            "status": "success",
            "device": current_device,
            "preview_source": preview_source,
            "preview_label": f"scrcpy · {current_device}",
            "captured_at": result.get("captured_at", int(time.time() * 1000)),
            "screenshot_url": "",  # scrcpy 流模式下不走静态截图 URL
            "jpeg_base64": base64.b64encode(result["bytes"]).decode("ascii"),
        }

    if preview_source == PREVIEW_SOURCE_CAPTURE_CARD:
        try:
            result = capture_card_service.capture_preview()
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc))

        screenshot_name = Path(result["path"]).name
        captured_at = int(result["captured_at"])
        return {
            "status": "success",
            "device": "",
            "preview_source": preview_source,
            "preview_label": result.get("label", "采集卡"),
            "captured_at": captured_at,
            "screenshot_url": f"/api/screenshot/{screenshot_name}?ts={captured_at}",
        }

    current_device = get_current_device_state()
    if not current_device:
        raise HTTPException(status_code=400, detail="请先选择设备")

    controller = get_controller()
    # take_screenshot 是阻塞 ADB 调用（adb exec-out screencap），必须在线程池执行，
    # 否则设备响应慢/无响应时会冻结整个事件循环，导致其它接口全部超时。
    screenshot_path = await asyncio.to_thread(controller.take_screenshot, f"device_preview_{current_device}")
    if not screenshot_path:
        raise HTTPException(status_code=502, detail="获取设备画面失败")

    screenshot_name = Path(screenshot_path).name
    captured_at = int(time.time() * 1000)
    return {
        "status": "success",
        "device": current_device,
        "preview_source": preview_source,
        "preview_label": current_device,
        "captured_at": captured_at,
        "screenshot_url": f"/api/screenshot/{screenshot_name}?ts={captured_at}",
    }


@router.get("/preview/stream")
async def get_device_preview_stream(source: Annotated[str, Query(description="预览来源: capture_card / scrcpy")] = PREVIEW_SOURCE_CAPTURE_CARD):
    """获取采集卡或 scrcpy 的实时预览流。"""
    preview_source = _normalize_preview_source(source)

    if preview_source == PREVIEW_SOURCE_SCRCPY:
        current_device = get_current_device_state()
        if not current_device:
            raise HTTPException(status_code=400, detail="请先选择设备")
        try:
            first_frame = scrcpy_service.capture_encoded_frame()
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        return StreamingResponse(
            _iter_scrcpy_preview_stream(first_frame),
            media_type=f"multipart/x-mixed-replace; boundary={PREVIEW_STREAM_BOUNDARY.decode('ascii')}",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    if preview_source != PREVIEW_SOURCE_CAPTURE_CARD:
        raise HTTPException(status_code=400, detail="实时预览仅支持采集卡或 scrcpy 来源")

    try:
        first_frame = capture_card_service.capture_encoded_frame()
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return StreamingResponse(
        _iter_capture_card_preview_stream(first_frame),
        media_type=f"multipart/x-mixed-replace; boundary={PREVIEW_STREAM_BOUNDARY.decode('ascii')}",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/capture-card/devices")
async def list_capture_card_devices():
    """枚举本机当前可用的视频采集设备。"""
    try:
        devices = capture_card_service.list_capture_devices()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"枚举采集卡设备失败: {exc}")

    active = capture_card_service.get_active_device()
    return {
        "devices": devices,
        "active_device": active,
    }


@router.get("/capture-card/active")
async def get_capture_card_active_device():
    """返回当前生效的采集卡设备 device_id / label。"""
    return {"active_device": capture_card_service.get_active_device()}


@router.post("/capture-card/active")
async def set_capture_card_active_device(request: CaptureCardDeviceSelectRequest):
    """切换采集卡设备并持久化。"""
    try:
        active = capture_card_service.set_active_device(request.device_id, request.label)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {"status": "success", "active_device": active}


@router.post("/capture-card/release")
async def release_capture_card():
    """主动释放采集卡设备占用。"""
    try:
        capture_card_service.release()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"释放采集卡失败: {exc}")

    return {"status": "success", "message": "采集卡设备已释放"}


@router.post("/preview/save")
async def save_device_preview(request: DevicePreviewSaveRequest):
    """保存框选后的设备预览截图。"""
    image_base64 = str(request.image_base64 or '').strip()
    if not image_base64:
        raise HTTPException(status_code=400, detail="缺少截图数据")

    try:
        image_bytes = base64.b64decode(image_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="截图数据无效")

    if not image_bytes:
        raise HTTPException(status_code=400, detail="截图数据为空")

    save_dir = _resolve_preview_save_dir(request.save_dir)
    if save_dir.exists() and not save_dir.is_dir():
        raise HTTPException(status_code=400, detail="保存地址不是文件夹")

    try:
        save_dir.mkdir(parents=True, exist_ok=True)
        if request.overwrite:
            file_name = _build_preview_overwrite_file_name(request.file_name)
        else:
            file_name = _build_unique_preview_file_name(save_dir, request.file_name)
        save_path = save_dir / file_name
        save_path.write_bytes(image_bytes)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"保存截图失败: {exc}")

    return {
        "status": "success",
        "file_name": file_name,
        "saved_path": str(save_path),
        "save_dir": str(save_dir),
        "image_ref": _build_preview_image_reference(save_path),
    }

@router.post("/commands/execute")
async def execute_commands(request: CommandExecuteRequest):
    """执行命令序列"""
    current_device = get_current_device_state()
    if not current_device:
        raise HTTPException(status_code=400, detail="请先选择设备")

    controller = get_controller()
    # ADB 下发是阻塞 IO，扔到线程池避免卡住事件循环（其它接口在执行步骤时仍然要响应）
    results = await asyncio.to_thread(controller.execute_commands, request.commands)
    return {"results": results}

@router.post("/commands/stop")
async def stop_command_execution():
    """停止当前命令序列执行"""
    controller = get_controller()
    stopped = controller.request_stop()
    return {"status": "success", "stopped": stopped}

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
    execution_results = await asyncio.to_thread(controller.execute_commands, command)
    return {
        "execution_results": execution_results,
        "executed_command": command
    }


@router.get("/scrcpy/status")
async def get_scrcpy_status():
    """返回 scrcpy 串流服务当前状态。"""
    return {"status": scrcpy_service.get_status()}


@router.post("/scrcpy/release")
async def release_scrcpy():
    """释放 scrcpy 子进程占用。"""
    try:
        scrcpy_service.release()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"释放 scrcpy 失败: {exc}")
    return {"status": "success", "message": "scrcpy 进程已释放"}
