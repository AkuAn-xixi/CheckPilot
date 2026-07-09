"""命令执行API路由模块"""
import os
import asyncio
import json
import logging
import math
import re
import time
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from ..runtime import get_controller, get_current_device
from ..utils.adb_controller import KEYCODE_MAP, NON_EXECUTABLE_KEYS, apply_min_command_delay, get_keycode_map
from ..utils.path_resolver import resolve_excel_file, resolve_image_file
from ..services.image_compare_service import (
    ImageCompareRuntimeError,
    image_compare_service,
    verify_image_base64_match,
    verify_image_match,
)
from ..services.excel_service import excel_service
from ..services.capture_card_service import capture_card_service
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/excel", tags=["execution"])
WAIT_KEEPALIVE_INTERVAL = 15.0


class ExecutionStopped(Exception):
    """Raised when the client stops listening to the execution stream."""


class ImageModelSelectRequest(BaseModel):
    model_name: str


class ImageModelDownloadRequest(BaseModel):
    model_name: str = image_compare_service.DEFAULT_MODEL_NAME
    repo_id: str = image_compare_service.DEFAULT_REPO_ID

def format_sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def format_sse_comment(comment: str = "keepalive") -> str:
    return f": {comment}\n\n"


def get_valid_row(valid_rows: list, row_index: int) -> dict:
    if 1 <= row_index <= len(valid_rows):
        return valid_rows[row_index - 1]
    return {}


def build_compare_details(result: dict) -> dict:
    detail_keys = (
        "score",
        "template_score",
        "structure_score",
        "feature_score",
        "color_score",
        "dino_score",
        "aspect_ratio_score",
    )
    details = {}
    for key in detail_keys:
        value = result.get(key)
        if value in (None, ""):
            continue
        details[key] = value
    return details


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


async def stream_wait_with_heartbeat(
    delay: float,
    request: Request | None,
    *,
    interval: float = 0.1,
    heartbeat_interval: float | None = None,
):
    remaining = max(0.0, float(delay))
    heartbeat_interval = WAIT_KEEPALIVE_INTERVAL if heartbeat_interval is None else max(0.0, float(heartbeat_interval))
    heartbeat_remaining = max(0.0, float(heartbeat_interval))

    while remaining > 0:
        await ensure_execution_active(request)
        step = min(interval, remaining)
        await asyncio.sleep(step)
        remaining -= step

        if heartbeat_interval <= 0 or remaining <= 0:
            continue

        heartbeat_remaining -= step
        if heartbeat_remaining <= 0:
            heartbeat_remaining = heartbeat_interval
            yield format_sse_comment(f"waiting {math.ceil(remaining)}s")


async def stream_row_command_events(valid_rows: list, row_index: int, request: Request | None = None):
    """复用 Excel 解析结果，逐条输出命令执行事件。"""
    controller = get_controller()
    row_data = get_valid_row(valid_rows, row_index)
    commands = row_data.get("commands", [])
    logger.info("[执行] 共 %d 条命令待执行", len(commands))

    first_command = True
    for cmd in commands:
        await ensure_execution_active(request)

        if cmd.strip().lower() == 'nan':
            continue

        parts = cmd.strip().split('/')
        if len(parts) != 3:
            logger.warning("[执行] 命令格式错误: %s", cmd)
            yield {'status': 'error', 'message': f'命令格式错误: {cmd}'}
            continue

        keyname, repeat, delay = parts
        keyname = keyname.upper()

        if keyname not in get_keycode_map():
            logger.warning("[执行] 未知按键: %s", keyname)
            yield {'status': 'error', 'message': f'未知按键: {keyname}'}
            continue

        try:
            repeat = int(repeat)
            delay = apply_min_command_delay(float(delay))
        except ValueError:
            logger.warning("[执行] 命令参数错误: %s", cmd)
            yield {'status': 'error', 'message': f'命令参数错误: {cmd}'}
            continue

        if keyname in NON_EXECUTABLE_KEYS:
            if keyname == 'ASSERT':
                # ASSERT 触发"截图 + 图片校验"流程，由上层 execute_commands_stream 接管。
                # 这里 yield 一个内部占位事件，每发一次代表执行一次校验。
                # repeat>1 时按重复次数发多次（少见，但保留语义）；delay 在每次校验后等待。
                for _ in range(repeat):
                    yield {'__assert_check__': True}
                    if delay > 0:
                        async for keepalive in stream_wait_with_heartbeat(delay, request):
                            yield keepalive
            else:
                # 其它非执行按键保持原"跳过 + 等待 delay"语义
                yield {'status': 'info', 'message': f'已跳过非执行按键: {keyname}'}
                for _ in range(repeat):
                    await ensure_execution_active(request)
                    if delay > 0:
                        if delay >= WAIT_KEEPALIVE_INTERVAL:
                            yield {
                                'status': 'info',
                                'message': f'已跳过 {keyname}，等待约 {math.ceil(delay)} 秒后执行下一条命令',
                            }
                        async for keepalive in stream_wait_with_heartbeat(delay, request):
                            yield keepalive
            continue

        keycode = get_keycode_map()[keyname]
        logger.info("[执行] 命令解析: keyname=%s, keycode=%d, repeat=%d, delay=%.2fs",
                    keyname, keycode, repeat, delay)

        for i in range(repeat):
            await ensure_execution_active(request)
            repeat_label = f' ({i + 1}/{repeat})' if repeat > 1 else ''
            if first_command:
                first_command = False
                await wait_with_cancellation(0.3, request)
            else:
                await wait_with_cancellation(0.01, request)

            # 记录按键发送前的时间，用于精确计算剩余延迟
            send_started = time.perf_counter()
            ok = controller.send_keyevent(keycode, keyname, 0)
            elapsed_ms = (time.perf_counter() - send_started) * 1000
            if ok:
                yield {'status': 'success', 'message': f'✓ {keyname}{repeat_label} 发送成功 (耗时{elapsed_ms:.0f}ms)'}
            else:
                yield {'status': 'error', 'message': f'✗ {keyname}{repeat_label} 发送失败'}

            # 从按键发送起算，等待 delay 秒再执行下一次
            remaining_delay = max(0.0, delay - (time.perf_counter() - send_started))
            if remaining_delay > 0:
                if remaining_delay >= WAIT_KEEPALIVE_INTERVAL:
                    yield {
                        'status': 'info',
                        'message': f'已发送 {keyname}，等待约 {math.ceil(remaining_delay)} 秒后执行下一条命令'
                    }
                async for keepalive in stream_wait_with_heartbeat(remaining_delay, request):
                    yield keepalive


async def execute_commands_stream(
    request: Request,
    file_name: str,
    row_index: int,
    file_path: str,
    valid_rows: list,
    verify_image_base64: str = "",
    verify_image_missing: bool = False,
    verify_image_base64_list: list | None = None,
    verify_image_missing_list: list | None = None,
    match_threshold: float = 0.8,
    screenshot_source: str = "adb",
    enable_verification: bool = True,
    enable_recording: bool = True,
):
    """执行命令并生成流式响应。

    新规则：preScript 中如果出现 ``Assert/1/1``，每出现一次就在当前位置截图 + 校验
    一次，每次校验对应 ``checkPic`` 列里第 N 张图（按逗号顺序）。所有校验都通过才算
    PASS；任意 FAIL→FAIL，任意 ERROR→ERROR。
    没有 ASSERT 时退化为旧逻辑：跑完所有指令再做一次截图 + 校验。
    """
    controller = get_controller()
    executed_row = get_valid_row(valid_rows, row_index)
    test_title = executed_row.get("title") or None
    logger.info("[执行] ════════════════════════════════════════")
    logger.info("[执行] 开始执行: file=%s, row=%d, title=%s, screenshot_source=%s", file_name, row_index, test_title or '无', screenshot_source)

    # 启动录屏
    recording_started = False
    if enable_recording:
        ts_label = int(time.time() * 1000)
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', test_title or f"row_{row_index}")
        recording_filename = f"{safe_title}_{ts_label}.mp4"
        settings.RECORDING_DIR.mkdir(parents=True, exist_ok=True)
        recording_path = str(settings.RECORDING_DIR / recording_filename)
        if screenshot_source == "capture_card":
            recording_started = capture_card_service.start_recording(recording_path)
        else:
            recording_started = controller.start_recording(recording_path)
        if recording_started:
            logger.info("[执行] 录屏已启动: %s", recording_filename)
        else:
            logger.warning("[执行] 录屏启动失败，继续执行")

    # 多张校验图：拆分 checkPic 列里逗号分隔的文件名，与 base64 / missing 数组对齐
    verify_image_raw = str(executed_row.get('verify_image', '') or '')
    verify_image_list = [
        os.path.basename(item.strip())
        for item in verify_image_raw.split(',')
        if item.strip()
    ]
    logger.info("[执行] checkPic 列表: %s", verify_image_list if verify_image_list else '无')
    verify_image_base64_list = list(verify_image_base64_list or [])
    verify_image_missing_list = list(verify_image_missing_list or [])
    # 兼容老字段：单张时拷贝到列表
    if not verify_image_base64_list and verify_image_base64:
        verify_image_base64_list = [verify_image_base64]
    if not verify_image_missing_list and verify_image_missing:
        verify_image_missing_list = [verify_image_missing]

    def _verify_image_base64_at(idx: int) -> str:
        if 0 <= idx < len(verify_image_base64_list):
            return verify_image_base64_list[idx] or ''
        return ''

    def _verify_image_missing_at(idx: int) -> bool:
        if 0 <= idx < len(verify_image_missing_list):
            return bool(verify_image_missing_list[idx])
        return False

    def _write_test_result(result_value: str) -> None:
        """将执行结果写回 Excel 的 testResult 列。"""
        try:
            excel_row = executed_row.get("row")
            if not excel_row:
                logger.warning("[执行] 写回 testResult 跳过：无行号信息")
                return
            data_row_index = int(excel_row) - 2
            if data_row_index < 0:
                logger.warning("[执行] 写回 testResult 跳过：data_row_index=%d < 0", data_row_index)
                return
            excel_service.write_cell(file_name, "testResult", data_row_index, result_value)
            logger.info("[执行] 已写回 testResult=%s -> %s 第 %d 行", result_value, file_name, data_row_index)
        except Exception as e:
            logger.error("[执行] 写回 testResult 失败: %s", e)

    async def _take_screenshot_for_verify(suffix: str = ''):
        """截图并返回 (screenshot_path, screenshot_url)，失败时分别为 (None, None) 并 yield 错误。

        suffix 用来给同一行的多次截图取不同文件名，防止 ASSERT 多次校验时被覆盖。
        screenshot_source 控制截图来源："adb"（默认）或 "capture_card"。
        """
        await ensure_execution_active(request)
        title_for_screenshot = test_title
        if suffix:
            base = test_title or 'screenshot'
            title_for_screenshot = f"{base}_{suffix}"

        if screenshot_source == "capture_card":
            logger.info("[执行] 正在从采集卡截图: title=%s", title_for_screenshot)
            try:
                safe_name = re.sub(r'[\\/:*?"<>|]', '_', title_for_screenshot or 'capture_card')
                result = await asyncio.to_thread(capture_card_service.capture_preview, safe_name)
                screenshot_path = result.get("path")
                if not screenshot_path:
                    logger.error("[执行] 采集卡截图失败: 未返回文件路径")
                    return None, None
                screenshot_url = f"/api/screenshot/{os.path.basename(screenshot_path)}"
                logger.info("[执行] 采集卡截图成功: path=%s", screenshot_path)
                return screenshot_path, screenshot_url
            except Exception as e:
                logger.error("[执行] 采集卡截图异常: %s", e)
                return None, None
        else:
            logger.info("[执行] 正在截图: title=%s", title_for_screenshot)
            screenshot_path = controller.take_screenshot(title_for_screenshot)
            if not screenshot_path:
                logger.error("[执行] 截图失败: title=%s", title_for_screenshot)
                return None, None
            screenshot_url = f"/api/screenshot/{os.path.basename(screenshot_path)}"
            logger.info("[执行] 截图成功: path=%s", screenshot_path)
            return screenshot_path, screenshot_url

    def _do_verify(screenshot_path: str, target_image_name: str, base64_data: str) -> dict:
        """对一张图做比对，返回 verify_result（image_compare_service 风格的 dict）。"""
        if base64_data:
            logger.info("[校验] 使用 base64 数据比对: screenshot=%s, threshold=%.2f", screenshot_path, match_threshold)
            result = verify_image_base64_match(screenshot_path, base64_data, threshold=match_threshold)
            logger.info("[校验] base64 比对完成: matched=%s, score=%.4f, engine=%s",
                        result.get('matched'), result.get('score', 0.0), result.get('engine', 'opencv'))
            return result
        if not target_image_name:
            logger.warning("[校验] 校验图片名称为空")
            return {'success': False, 'matched': False, 'message': '校验图片名称为空', 'score': 0.0, 'engine': 'opencv', 'model_name': ''}
        icon_path = resolve_image_file(target_image_name, excel_file_name=file_name)
        if not icon_path.exists():
            logger.warning("[校验] 校验图片未找到: %s (resolved=%s)", target_image_name, icon_path)
            return {'success': False, 'matched': False, 'message': f'校验图片未找到: {target_image_name}', 'score': 0.0, 'engine': 'opencv', 'model_name': ''}
        logger.info("[校验] 文件路径比对: screenshot=%s, icon=%s, threshold=%.2f", screenshot_path, icon_path, match_threshold)
        result = verify_image_match(screenshot_path, str(icon_path), threshold=match_threshold)
        logger.info("[校验] 比对完成: matched=%s, score=%.4f, engine=%s",
                    result.get('matched'), result.get('score', 0.0), result.get('engine', 'opencv'))
        return result

    assert_results: list[dict] = []
    last_screenshot_url = ''

    async def _run_one_assert_check(assert_index: int):
        """执行一次"截图 + 比对"校验流程，结果累积进 assert_results 并 yield SSE 事件。"""
        nonlocal last_screenshot_url
        target_image = verify_image_list[assert_index] if assert_index < len(verify_image_list) else ''
        logger.info("[执行] ── 第 %d 次校验开始 (target=%s) ──", assert_index + 1, target_image or '无')

        yield format_sse({
            'status': 'info',
            'message': f'第 {assert_index + 1} 次校验：正在截图...',
            'assert_index': assert_index,
        })
        await wait_with_cancellation(0.4, request)
        screenshot_path, screenshot_url = await _take_screenshot_for_verify(
            suffix=f"assert_{assert_index + 1}_{int(time.time() * 1000)}",
        )
        if not screenshot_path:
            logger.error("[执行] 第 %d 次校验失败：截图失败", assert_index + 1)
            record = {
                'assert_index': assert_index,
                'verify_image': target_image,
                'screenshot_url': '',
                'verify_result': 'ERROR',
                'score': 0.0,
                'message': '截图失败',
                'compare_engine': 'opencv',
                'model_name': '',
            }
            assert_results.append(record)
            yield format_sse({
                'status': 'error',
                'message': f'第 {assert_index + 1} 次校验失败：截图失败',
                **record,
            })
            return

        last_screenshot_url = screenshot_url

        if not target_image:
            logger.error("[执行] 第 %d 次校验失败：缺少对应的 checkPic 图片", assert_index + 1)
            record = {
                'assert_index': assert_index,
                'verify_image': '',
                'screenshot_url': screenshot_url,
                'verify_result': 'ERROR',
                'score': 0.0,
                'message': f'第 {assert_index + 1} 次校验缺少对应的 checkPic 图片',
                'compare_engine': 'opencv',
                'model_name': '',
            }
            assert_results.append(record)
            yield format_sse({'status': 'error', **record})
            return

        if _verify_image_missing_at(assert_index):
            logger.error("[执行] 第 %d 次校验失败：校验图片未在本地文件夹中找到: %s", assert_index + 1, target_image)
            record = {
                'assert_index': assert_index,
                'verify_image': target_image,
                'screenshot_url': screenshot_url,
                'verify_result': 'ERROR',
                'score': 0.0,
                'message': f'校验图片未在本地文件夹中找到: {target_image}',
                'compare_engine': 'opencv',
                'model_name': '',
            }
            assert_results.append(record)
            yield format_sse({'status': 'error', **record})
            return

        yield format_sse({
            'status': 'info',
            'message': f'第 {assert_index + 1} 次校验：正在比对 {target_image}...',
            'assert_index': assert_index,
        })
        await wait_with_cancellation(0.2, request)

        verify_result = _do_verify(
            screenshot_path,
            target_image,
            _verify_image_base64_at(assert_index),
        )
        compare_details = build_compare_details(verify_result) if verify_result.get('success') else []

        if not verify_result.get('success'):
            logger.error("[执行] 第 %d 次校验比对出错: %s", assert_index + 1, verify_result.get('message', '未知错误'))
            record = {
                'assert_index': assert_index,
                'verify_image': target_image,
                'screenshot_url': screenshot_url,
                'verify_result': 'ERROR',
                'score': verify_result.get('score', 0.0),
                'message': f"比对出错: {verify_result.get('message', '未知错误')}",
                'compare_engine': verify_result.get('engine', 'opencv'),
                'model_name': verify_result.get('model_name', ''),
                'compare_details': compare_details,
            }
            assert_results.append(record)
            yield format_sse({'status': 'error', **record})
            return

        matched = bool(verify_result.get('matched'))
        score = verify_result.get('score', 0.0)
        if matched:
            logger.info("[执行] 第 %d 次校验通过 ✓ score=%.4f, target=%s", assert_index + 1, score, target_image)
        else:
            logger.warning("[执行] 第 %d 次校验失败 ✗ score=%.4f, target=%s", assert_index + 1, score, target_image)
        record = {
            'assert_index': assert_index,
            'verify_image': target_image,
            'screenshot_url': screenshot_url,
            'verify_result': 'PASS' if matched else 'FAIL',
            'score': score,
            'message': '验证成功: 图标匹配' if matched else '验证失败: 图标不匹配',
            'compare_engine': verify_result.get('engine', 'opencv'),
            'model_name': verify_result.get('model_name', ''),
            'compare_details': compare_details,
        }
        assert_results.append(record)
        yield format_sse({
            'status': 'success' if matched else 'error',
            **record,
        })

    try:
        async for event in stream_row_command_events(valid_rows, row_index, request):
            # ASSERT 触发的截图 + 校验占位事件
            if isinstance(event, dict) and event.get('__assert_check__'):
                if enable_verification:
                    async for emitted in _run_one_assert_check(len(assert_results)):
                        yield emitted
                continue

            # 普通命令事件
            if isinstance(event, str):
                yield event
            else:
                yield format_sse(event)

        # 所有指令跑完后，如果 verify_image_list 还有未消费的图（用户在 checkPic 列里多
        # 留了一张作为"末尾隐含 Assert"），自动再触发一次校验。
        if enable_verification:
            while len(assert_results) < len(verify_image_list):
                async for emitted in _run_one_assert_check(len(assert_results)):
                    yield emitted

        # 做汇总
        if assert_results:
            statuses = [r['verify_result'] for r in assert_results]
            if any(s == 'ERROR' for s in statuses):
                overall = 'ERROR'
            elif all(s == 'PASS' for s in statuses):
                overall = 'PASS'
            else:
                overall = 'FAIL'

            _write_test_result(overall)
            overall_message = (
                f'最终结果：{overall}（{statuses.count("PASS")}/{len(statuses)} 通过）'
            )
            logger.info("[执行] %s", overall_message)
            logger.info("[执行] 各项详情: %s", [
                f"#{r['assert_index']+1}:{r['verify_result']}({r['score']:.2f})" for r in assert_results
            ])
            logger.info("[执行] ════════════════════════════════════════")

            # 停止录屏
            video_url = ""
            if recording_started:
                await asyncio.sleep(2)  # 多录 2 秒，确保最后操作完整
                if screenshot_source == "capture_card":
                    video_path = capture_card_service.stop_recording_and_convert()
                else:
                    video_path = controller.stop_recording()
                if video_path:
                    video_url = f"/api/recording/{os.path.basename(video_path)}"
                    logger.info("[执行] 录屏已保存: %s（后台正在转换为 H.264，约需 1-2 分钟）", video_url)

            yield format_sse({
                'status': 'success' if overall == 'PASS' else 'error',
                'message': overall_message,
                'verify_result': overall,
                'multi_verify_results': assert_results,
                'screenshot_url': last_screenshot_url,
                'video_url': video_url,
                'video_converting': screenshot_source == "capture_card",
            })
            return

        # 关闭校验时：直接产出"跳过校验"的结果并结束
        if not enable_verification:
            logger.info("[执行] 校验已关闭，跳过截图校验")
            _write_test_result('NT')

            # 停止录屏
            video_url = ""
            if recording_started:
                await asyncio.sleep(2)
                if screenshot_source == "capture_card":
                    video_path = capture_card_service.stop_recording_and_convert()
                else:
                    video_path = controller.stop_recording()
                if video_path:
                    video_url = f"/api/recording/{os.path.basename(video_path)}"
                    logger.info("[执行] 录屏已保存: %s", video_url)

            yield format_sse({
                'status': 'success',
                'message': '执行完成（校验已跳过）',
                'verify_result': 'NT',
                'video_url': video_url,
            })
            return

        else:
            # 没有 ASSERT 也没有 verify_image：退化到原有"末尾一次截图 + 一次比对"
            logger.info("[执行] 无 ASSERT 指令，走末尾单次截图校验逻辑")
            await ensure_execution_active(request)
            yield format_sse({'status': 'info', 'message': '正在截图...'})
            await wait_with_cancellation(0.4, request)

            if screenshot_source == "capture_card":
                try:
                    safe_name = re.sub(r'[\\/:*?"<>|]', '_', test_title or 'capture_card')
                    capture_result = await asyncio.to_thread(capture_card_service.capture_preview, safe_name)
                    screenshot_path = capture_result.get("path")
                except Exception as e:
                    logger.error("[执行] 采集卡截图异常: %s", e)
                    screenshot_path = None
            else:
                screenshot_path = controller.take_screenshot(test_title)
            if screenshot_path:
                screenshot_url = f"/api/screenshot/{os.path.basename(screenshot_path)}"
                yield format_sse({'status': 'success', 'message': '截图成功', 'screenshot_url': screenshot_url})

                if executed_row:
                    verify_image = executed_row.get('verify_image', '')

                    if verify_image:
                        if verify_image_missing or _verify_image_missing_at(0):
                            logger.error("[执行] 末尾校验失败：校验图片未在本地文件夹中找到: %s", verify_image)
                            yield format_sse({'status': 'error', 'message': f'校验图片未在本地文件夹中找到: {verify_image}，请检查校验图片文件夹是否包含该图片，或重新选择校验图片文件夹'})
                            return

                        await ensure_execution_active(request)
                        yield format_sse({'status': 'info', 'message': '正在验证图片...'})
                        await wait_with_cancellation(0.2, request)

                        if verify_image_base64 or _verify_image_base64_at(0):
                            verify_result = verify_image_base64_match(
                                screenshot_path,
                                verify_image_base64 or _verify_image_base64_at(0),
                                threshold=match_threshold,
                            )
                        else:
                            icon_path = resolve_image_file(verify_image, excel_file_name=file_name)
                            if not icon_path.exists():
                                yield format_sse({'status': 'error', 'message': f'校验图片未找到: {verify_image}'})
                                return

                            verify_result = verify_image_match(screenshot_path, str(icon_path), threshold=match_threshold)

                        if verify_result['success']:
                            compare_details = build_compare_details(verify_result)
                            result_meta = {
                                'compare_engine': verify_result.get('engine', 'opencv'),
                                'model_name': verify_result.get('model_name', ''),
                                'compare_details': compare_details,
                            }
                            if verify_result['matched']:
                                _write_test_result('PASS')
                            logger.info("[执行] 末尾校验通过 ✓ score=%.4f", verify_result['score'])
                            yield format_sse({'status': 'success', 'message': '验证成功: 图标匹配', 'verify_result': 'PASS', 'score': verify_result['score'], **result_meta})
                        else:
                            _write_test_result('FAIL')
                            logger.warning("[执行] 末尾校验失败 ✗ score=%.4f", verify_result['score'])
                            yield format_sse({'status': 'error', 'message': '验证失败: 图标不匹配', 'verify_result': 'FAIL', 'score': verify_result['score'], **result_meta})
                    else:
                        _write_test_result('ERROR')
                        logger.error("[执行] 末尾校验出错: %s", verify_result.get('message', ''))
                        message = f'验证过程出错: {verify_result["message"]}'
                        yield format_sse({
                            'status': 'error',
                            'message': message,
                            'compare_engine': verify_result.get('engine', 'opencv'),
                            'model_name': verify_result.get('model_name', ''),
                        })
            else:
                logger.error("[执行] 末尾截图失败")
                yield format_sse({'status': 'error', 'message': '截图失败'})

        # 停止录屏（末尾校验分支也需要处理）
        if recording_started:
            await asyncio.sleep(2)  # 多录 2 秒，确保最后操作完整
            if screenshot_source == "capture_card":
                video_path = capture_card_service.stop_recording_and_convert()
            else:
                video_path = controller.stop_recording()
            if video_path:
                video_url = f"/api/recording/{os.path.basename(video_path)}"
                logger.info("[执行] 录屏已保存: %s", video_url)
                yield format_sse({'status': 'info', 'video_url': video_url})

        logger.info("[执行] ════════════════════════════════════════")
    except ExecutionStopped:
        # 停止录屏（异常退出也要清理）
        if recording_started:
            if screenshot_source == "capture_card":
                capture_card_service.stop_recording()
            else:
                controller.stop_recording()
        logger.info("[执行] 客户端断开连接，执行中止: file=%s, row=%d", file_name, row_index)
        return


@router.get("/image-models/status")
async def get_image_model_status():
    """返回图片比对模型状态；未选择模型时默认使用 OpenCV。"""
    return image_compare_service.get_status()


@router.post("/image-models/download")
async def download_image_model(request: ImageModelDownloadRequest):
    """下载 DINOv2 图片比对模型到运行时目录。"""
    try:
        return image_compare_service.download_model(request.model_name, request.repo_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ImageCompareRuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载图片模型失败: {str(e)}")


@router.post("/image-models/select")
async def select_image_model(request: ImageModelSelectRequest):
    """切换当前图片比对模型。"""
    try:
        return image_compare_service.set_active_model(request.model_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"切换图片模型失败: {str(e)}")


@router.post("/image-models/clear-selection")
async def clear_selected_image_model():
    """取消当前图片模型选择，回退为 OpenCV。"""
    try:
        return image_compare_service.clear_active_model()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"切换 OpenCV 失败: {str(e)}")


@router.delete("/image-models")
async def delete_image_model(model_name: str):
    """删除运行时图片模型目录。"""
    try:
        return image_compare_service.delete_model(model_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除图片模型失败: {str(e)}")

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
    verify_image_missing = body.get('verify_image_missing', False)
    verify_image_base64_list = body.get('verify_image_base64_list') or []
    verify_image_missing_list = body.get('verify_image_missing_list') or []
    match_threshold = float(body.get('match_threshold', 0.8) or 0.8)
    screenshot_source = str(body.get('screenshot_source', 'adb') or 'adb').strip().lower()
    enable_verification = bool(body.get('enable_verification', True))
    enable_recording = bool(body.get('enable_recording', True))
    if screenshot_source not in ('adb', 'capture_card'):
        screenshot_source = 'adb'

    logger.info("[执行] 收到执行请求: file=%s, row=%s, device=%s, verify_images=%d, missing=%d, screenshot_source=%s",
                file_name, row_index, current_device,
                len(verify_image_base64_list), sum(1 for m in verify_image_missing_list if m),
                screenshot_source)

    if not file_name or not row_index:
        raise HTTPException(status_code=400, detail="请提供文件名和行号")

    try:
        row_index = int(row_index)
    except ValueError:
        raise HTTPException(status_code=400, detail="行号必须是整数")

    file_path = resolve_excel_file(file_name)
    if not file_path.exists():
        logger.error("[执行] 文件不存在: %s", file_path)
        raise HTTPException(status_code=404, detail="文件不存在")

    controller = get_controller()
    result = controller.read_excel_commands(str(file_path), row_index)
    valid_rows = result.get("valid_rows", [])
    logger.info("[执行] Excel 解析完成: 共 %d 个有效行", len(valid_rows))

    logger.info("[执行] 匹配阈值: %.2f", match_threshold)

    return StreamingResponse(
        execute_commands_stream(
            request,
            file_name,
            row_index,
            str(file_path),
            valid_rows,
            verify_image_base64=verify_image_base64,
            verify_image_missing=verify_image_missing,
            verify_image_base64_list=verify_image_base64_list,
            verify_image_missing_list=verify_image_missing_list,
            match_threshold=match_threshold,
            screenshot_source=screenshot_source,
            enable_verification=enable_verification,
            enable_recording=enable_recording,
        ),
        media_type="text/event-stream"
    )
