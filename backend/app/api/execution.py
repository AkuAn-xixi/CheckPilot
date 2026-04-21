"""命令执行API路由模块"""
import os
import asyncio
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from app.runtime import get_controller, get_current_device
from app.utils.adb_controller import KEYCODE_MAP
from app.utils.path_resolver import resolve_excel_file, resolve_image_file
from app.services.image_service import verify_image_match, verify_image_base64_match

router = APIRouter(prefix="/api/excel", tags=["execution"])

async def execute_commands_stream(file_name: str, row_index: int, file_path: str, valid_rows: list, verify_image_base64: str = ""):
    """执行命令并生成流式响应"""
    controller = get_controller()
    current_device = get_current_device()

    commands = valid_rows[row_index - 1]["commands"] if row_index <= len(valid_rows) else []

    test_title = None
    if 1 <= row_index <= len(valid_rows):
        executed_row = valid_rows[row_index - 1]
        if "title" in executed_row and executed_row["title"]:
            test_title = executed_row["title"]

    for cmd in commands:
        if cmd.strip().lower() == 'nan':
            continue

        parts = cmd.strip().split('/')
        if len(parts) != 3:
            yield f"data: {json.dumps({'status': 'error', 'message': f'命令格式错误: {cmd}'})}\n\n"
            continue

        keyname, repeat, delay = parts
        keyname = keyname.upper()

        if keyname not in KEYCODE_MAP:
            yield f"data: {json.dumps({'status': 'error', 'message': f'未知按键: {keyname}'})}\n\n"
            continue

        try:
            repeat = int(repeat)
            delay = float(delay)
        except ValueError:
            yield f"data: {json.dumps({'status': 'error', 'message': f'命令参数错误: {cmd}'})}\n\n"
            continue

        keycode = KEYCODE_MAP[keyname]

        for _ in range(repeat):
            yield f"data: {json.dumps({'status': 'info', 'message': f'正在发送: {keyname}'})}\n\n"
            await asyncio.sleep(0.01)

            controller.send_keyevent(keycode, keyname, delay)
            await asyncio.sleep(0.1)

    yield f"data: {json.dumps({'status': 'info', 'message': '正在截图...'})}\n\n"
    await asyncio.sleep(0.4)

    screenshot_path = controller.take_screenshot(test_title)
    if screenshot_path:
        screenshot_url = f"/api/screenshot/{os.path.basename(screenshot_path)}"
        yield f"data: {json.dumps({'status': 'success', 'message': '截图成功', 'screenshot_url': screenshot_url})}\n\n"

        if 1 <= row_index <= len(valid_rows):
            executed_row = valid_rows[row_index - 1]
            verify_image = executed_row.get('verify_image', '')

            if verify_image:
                yield f"data: {json.dumps({'status': 'info', 'message': '正在验证图片...'})}\n\n"
                await asyncio.sleep(0.2)

                if verify_image_base64:
                    verify_result = verify_image_base64_match(screenshot_path, verify_image_base64)
                else:
                    icon_path = resolve_image_file(verify_image, excel_file_name=file_name)
                    if not icon_path.exists():
                        yield f"data: {json.dumps({'status': 'error', 'message': f'校验图片未找到: {verify_image}'})}\n\n"
                        return

                    verify_result = verify_image_match(screenshot_path, str(icon_path))

                if verify_result['success']:
                    if verify_result['matched']:
                        yield f"data: {json.dumps({'status': 'success', 'message': '验证成功: 图标匹配', 'verify_result': 'PASS', 'score': verify_result['score']})}\n\n"
                    else:
                        yield f"data: {json.dumps({'status': 'error', 'message': '验证失败: 图标不匹配', 'verify_result': 'FAIL', 'score': verify_result['score']})}\n\n"
                else:
                    message = f'验证过程出错: {verify_result["message"]}'
                    yield f"data: {json.dumps({'status': 'error', 'message': message})}\n\n"
    else:
        yield f"data: {json.dumps({'status': 'error', 'message': '截图失败'})}\n\n"

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
        execute_commands_stream(file_name, row_index, str(file_path), valid_rows, verify_image_base64=verify_image_base64),
        media_type="text/event-stream"
    )
