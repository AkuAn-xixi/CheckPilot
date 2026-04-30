"""命令执行API路由模块"""
import os
import asyncio
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from ..runtime import get_controller, get_current_device
from ..utils.adb_controller import KEYCODE_MAP, get_keycode_map
from ..utils.path_resolver import resolve_excel_file, resolve_image_file
from ..services.image_service import verify_image_match, verify_image_base64_match

router = APIRouter(prefix="/api/excel", tags=["execution"])


class ExecutionStopped(Exception):
    """Raised when the client stops listening to the execution stream."""

def format_sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def get_valid_row(valid_rows: list, row_index: int) -> dict:
    if 1 <= row_index <= len(valid_rows):
        return valid_rows[row_index - 1]
    return {}


async def ensure_execution_active(request: Request | None) -> None:
    if request is not None and await request.is_disconnected():
        raise ExecutionStopped()


async def wait_with_cancellation(delay: float, request: Request | None, interval: float = 0.1) -> None:
    remaining = max(0.0, float(delay))
    while remaining > 0:
        await ensure_execution_active(request)
        step = min(interval, remaining)
        await asyncio.sleep(step)
        remaining -= step


async def stream_row_command_events(valid_rows: list, row_index: int, request: Request | None = None):
    """复用 Excel 解析结果，逐条输出命令执行事件。"""
    controller = get_controller()
    row_data = get_valid_row(valid_rows, row_index)
    commands = row_data.get("commands", [])

    for cmd in commands:
        await ensure_execution_active(request)

        if cmd.strip().lower() == 'nan':
            continue

        parts = cmd.strip().split('/')
        if len(parts) != 3:
            yield {'status': 'error', 'message': f'命令格式错误: {cmd}'}
            continue

        keyname, repeat, delay = parts
        keyname = keyname.upper()

        if keyname not in get_keycode_map():
            yield {'status': 'error', 'message': f'未知按键: {keyname}'}
            continue

        try:
            repeat = int(repeat)
            delay = float(delay)
        except ValueError:
            yield {'status': 'error', 'message': f'命令参数错误: {cmd}'}
            continue

        keycode = get_keycode_map()[keyname]

        for _ in range(repeat):
            await ensure_execution_active(request)
            yield {'status': 'info', 'message': f'正在发送: {keyname}'}
            await wait_with_cancellation(0.01, request)

            controller.send_keyevent(keycode, keyname, 0)
            if delay > 0:
                await wait_with_cancellation(delay, request)
            await wait_with_cancellation(0.1, request)


async def execute_commands_stream(request: Request, file_name: str, row_index: int, file_path: str, valid_rows: list, verify_image_base64: str = ""):
    """执行命令并生成流式响应"""
    controller = get_controller()
    executed_row = get_valid_row(valid_rows, row_index)
    test_title = executed_row.get("title") or None

    try:
        async for event in stream_row_command_events(valid_rows, row_index, request):
            yield format_sse(event)

        await ensure_execution_active(request)
        yield format_sse({'status': 'info', 'message': '正在截图...'})
        await wait_with_cancellation(0.4, request)

        screenshot_path = controller.take_screenshot(test_title)
        if screenshot_path:
            screenshot_url = f"/api/screenshot/{os.path.basename(screenshot_path)}"
            yield format_sse({'status': 'success', 'message': '截图成功', 'screenshot_url': screenshot_url})

            if executed_row:
                verify_image = executed_row.get('verify_image', '')

                if verify_image:
                    await ensure_execution_active(request)
                    yield format_sse({'status': 'info', 'message': '正在验证图片...'})
                    await wait_with_cancellation(0.2, request)

                    if verify_image_base64:
                        verify_result = verify_image_base64_match(screenshot_path, verify_image_base64)
                    else:
                        icon_path = resolve_image_file(verify_image, excel_file_name=file_name)
                        if not icon_path.exists():
                            yield format_sse({'status': 'error', 'message': f'校验图片未找到: {verify_image}'})
                            return

                        verify_result = verify_image_match(screenshot_path, str(icon_path))

                    if verify_result['success']:
                        if verify_result['matched']:
                            yield format_sse({'status': 'success', 'message': '验证成功: 图标匹配', 'verify_result': 'PASS', 'score': verify_result['score']})
                        else:
                            yield format_sse({'status': 'error', 'message': '验证失败: 图标不匹配', 'verify_result': 'FAIL', 'score': verify_result['score']})
                    else:
                        message = f'验证过程出错: {verify_result["message"]}'
                        yield format_sse({'status': 'error', 'message': message})
        else:
            yield format_sse({'status': 'error', 'message': '截图失败'})
    except ExecutionStopped:
        return

@router.post("/execute")
async def execute_excel_commands(request: Request):
    """执行Excel文件中的命令"""
    current_device = get_current_device()
    if not current_device:
        raise HTTPException(status_code=400, detail="请先选择设备")

    body = await request.json()
    file_name = body.get('file_name')
    row_index = body.get('row_index')
    verify_image_base64 = body.get('verify_image_base64', '')

    if not file_name or not row_index:
        raise HTTPException(status_code=400, detail="请提供文件名和行号")

    try:
        row_index = int(row_index)
    except ValueError:
        raise HTTPException(status_code=400, detail="行号必须是整数")

    file_path = resolve_excel_file(file_name)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    controller = get_controller()
    result = controller.read_excel_commands(str(file_path), row_index)
    valid_rows = result.get("valid_rows", [])

    return StreamingResponse(
        execute_commands_stream(request, file_name, row_index, str(file_path), valid_rows, verify_image_base64=verify_image_base64),
        media_type="text/event-stream"
    )
