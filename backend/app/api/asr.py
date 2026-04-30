"""ASR API 路由模块"""
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..services.asr_service import AsrRuntimeError, asr_service
from ..services.excel_service import excel_service
from ..runtime import get_controller, get_current_device
from .execution import (
    ExecutionStopped,
    ensure_execution_active,
    format_sse,
    get_valid_row,
    stream_row_command_events,
    wait_with_cancellation,
)

router = APIRouter(prefix="/api/excel/asr", tags=["asr"])
TTS_MARKER = "TTS"


def _normalize_command_name(command: str) -> str:
    normalized = str(command or "").strip()
    if not normalized:
        return ""

    parts = normalized.split("/")
    return parts[0].strip().upper() if parts else normalized.upper()


def _is_tts_marker(command: str) -> bool:
    return _normalize_command_name(command) == TTS_MARKER


def _plan_asr_recording_commands(commands: list[str]) -> tuple[list[str], str, list[str], bool]:
    tts_indexes = [index for index, command in enumerate(commands) if _is_tts_marker(command)]
    if not tts_indexes:
        return commands[:-1], commands[-1], [], False

    if len(tts_indexes) > 1:
        raise AsrRuntimeError("当前 ASR 用例仅支持一个 TTS 标记")

    tts_index = tts_indexes[0]
    if tts_index >= len(commands) - 1:
        raise AsrRuntimeError("TTS 后缺少待录音的下一条命令")

    trigger_command = commands[tts_index + 1]
    if _is_tts_marker(trigger_command):
        raise AsrRuntimeError("TTS 后的下一条命令不能继续是 TTS")

    return commands[:tts_index], trigger_command, commands[tts_index + 2:], True


class AsrModelSelectRequest(BaseModel):
    model_name: str


@router.get("/status")
async def get_asr_status():
    """返回 Project 目录下旧 ASR 原型资源的探测结果。"""
    return asr_service.get_status()


@router.post("/models/import")
async def import_asr_model_file(
    model_name: str = Form(...),
    relative_path: str = Form(...),
    file: UploadFile = File(...),
):
    """导入 ASR 模型目录中的单个文件。前端按文件顺序调用此接口完成整目录导入。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="未选择模型文件")

    try:
        result = asr_service.save_imported_model_file(model_name, relative_path, file)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入模型失败: {str(e)}")
    finally:
        await file.close()


@router.post("/models/select")
async def select_asr_model(request: AsrModelSelectRequest):
    """切换当前 ASR 测试使用的模型目录。"""
    try:
        return asr_service.set_active_model(request.model_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"切换模型失败: {str(e)}")


@router.delete("/models")
async def delete_asr_model(model_name: str):
    """删除运行时 ASR 模型目录。"""
    try:
        return asr_service.delete_model(model_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除模型失败: {str(e)}")


async def execute_asr_commands_stream(request: Request, row_index: int, valid_rows: list):
    active_model = asr_service.get_active_model()
    if active_model is None:
        yield format_sse({"status": "error", "message": "请先导入并选择 ASR 模型"})
        return

    dependency_status = asr_service.get_runtime_dependency_status()
    missing_required = [
        name
        for name in dependency_status["missing"]
        if name in {"sounddevice", "qwen_asr", "torch"}
    ]
    if missing_required:
        missing_text = ", ".join(missing_required)
        yield format_sse({
            "status": "error",
            "message": f"ASR 运行依赖缺失: {missing_text}。请先按页面顶部提示安装依赖，重启后端后再刷新状态。",
            "missing_dependencies": missing_required,
            "install_commands": dependency_status.get("install_commands", []),
            "python_version": dependency_status.get("python_version", ""),
        })
        return

    executed_row = get_valid_row(valid_rows, row_index)
    case_title = executed_row.get("title") or f"第 {row_index} 行"
    commands = [command for command in executed_row.get("commands", []) if str(command or "").strip()]
    if not commands:
        yield format_sse({"status": "error", "message": "当前用例没有可执行命令"})
        return

    pre_record_commands, recorded_command, post_record_commands, uses_tts_marker = _plan_asr_recording_commands(commands)

    reference = asr_service.find_reference(case_title)
    recorder = None
    recording_started = False
    tts_text = ""

    try:
        await ensure_execution_active(request)
        yield format_sse({
            "status": "info",
            "message": f"已选择模型: {active_model['name']}"
        })
        yield format_sse({
            "status": "info",
            "message": f"开始执行 ASR 用例: {case_title}"
        })

        if reference is not None:
            yield format_sse({
                "status": "info",
                "message": f"已加载参考文本: {reference['path']}"
            })
        else:
            yield format_sse({
                "status": "info",
                "message": f"未找到用例 {case_title} 的参考文本，如捕获到 TTS 输出则将使用 TTS 文本进行比对"
            })

        if pre_record_commands:
            async for event in stream_row_command_events([{"commands": pre_record_commands}], 1, request):
                yield format_sse(event)

        await ensure_execution_active(request)
        recorder = asr_service.create_recorder()
        recorder.start_recording()
        recording_started = True
        yield format_sse({
            "status": "info",
            "message": "识别到 TTS 标记，开始录音，准备执行下一条命令" if uses_tts_marker else "开始录音，准备执行触发 ASR 的最后一步命令"
        })
        await wait_with_cancellation(0.5, request)

        async for event in stream_row_command_events([{"commands": [recorded_command]}], 1, request):
            yield format_sse(event)

        await wait_with_cancellation(0.3, request)

        controller = get_controller()
        tts_text = (controller.get_last_tts_text() or "").strip()
        if tts_text:
            yield format_sse({
                "status": "info",
                "message": f"TTS 输出文本: {tts_text}",
                "tts_text": tts_text,
            })
        else:
            yield format_sse({
                "status": "info",
                "message": "未捕获到 TTS 输出文本",
                "tts_text": "",
            })

        recorder.stop_recording()
        recording_started = False

        audio_path = asr_service.save_audio_recording(recorder, case_title)
        yield format_sse({
            "status": "info",
            "message": f"录音已保存: {audio_path}"
        })

        if post_record_commands:
            yield format_sse({
                "status": "info",
                "message": "TTS 录音窗口已结束，继续执行剩余命令"
            })
            async for event in stream_row_command_events([{"commands": post_record_commands}], 1, request):
                yield format_sse(event)

        await ensure_execution_active(request)
        yield format_sse({
            "status": "info",
            "message": "开始执行 ASR 识别..."
        })
        transcript = asr_service.transcribe_audio(audio_path)
        transcript_path = asr_service.save_transcript(audio_path, transcript)
        yield format_sse({
            "status": "info",
            "message": f"ASR 识别完成: {transcript or '识别结果为空'}",
            "transcribed_text": transcript,
            "transcript_path": str(transcript_path),
            "tts_text": tts_text,
        })

        reference_text = (reference or {}).get("text", "").strip() if reference else ""
        reference_path = (reference or {}).get("path", "") if reference else ""
        comparison_text = reference_text or tts_text
        comparison_source = "reference" if reference_text else "tts"

        if not comparison_text:
            yield format_sse({
                "status": "error",
                "message": "未找到参考文本，且未捕获到 TTS 文本，无法完成比对",
                "row_index": row_index,
                "asr_result": "NO_REF",
                "asr_score": None,
                "transcribed_text": transcript,
                "tts_text": tts_text,
                "audio_path": str(audio_path),
                "transcript_path": str(transcript_path),
            })
            return

        if not reference_text:
            yield format_sse({
                "status": "info",
                "message": "未找到参考文本，改用 TTS 输出文本进行比对",
                "reference_text": comparison_text,
                "tts_text": tts_text,
                "comparison_source": comparison_source,
            })

        comparison = asr_service.compare_transcript(transcript, comparison_text)
        compare_report_path = asr_service.save_compare_report(
            audio_path,
            transcript,
            comparison_text,
            comparison,
        )
        message = (
            f"ASR 比对 {comparison['result']}: 平均 {comparison['average'] * 100:.2f}% / "
            f"余弦 {comparison['cosine'] * 100:.2f}% / 序列 {comparison['sequence'] * 100:.2f}%"
        )
        yield format_sse({
            "status": "success" if comparison["matched"] else "error",
            "message": message,
            "row_index": row_index,
            "asr_result": comparison["result"],
            "asr_score": comparison["average"],
            "asr_cosine": comparison["cosine"],
            "asr_sequence": comparison["sequence"],
            "transcribed_text": transcript,
            "tts_text": tts_text,
            "reference_text": comparison_text,
            "reference_path": reference_path,
            "comparison_source": comparison_source,
            "audio_path": str(audio_path),
            "transcript_path": str(transcript_path),
            "compare_result_path": str(compare_report_path),
        })
    except ExecutionStopped:
        if recorder is not None and recording_started:
            recorder.stop_recording()
        return
    except AsrRuntimeError as exc:
        if recorder is not None and recording_started:
            recorder.stop_recording()
        yield format_sse({"status": "error", "message": str(exc)})
    except Exception as exc:
        if recorder is not None and recording_started:
            recorder.stop_recording()
        yield format_sse({"status": "error", "message": f"执行 ASR 用例失败: {str(exc)}"})


@router.post("/execute")
async def execute_asr_case(request: Request):
    """执行 ASR 测试用例，完成录音、识别与文本比对。"""
    current_device = get_current_device()
    if not current_device:
        raise HTTPException(status_code=400, detail="请先选择设备")

    body = await request.json()
    file_name = body.get("file_name")
    row_index = body.get("row_index")

    if not file_name or not row_index:
        raise HTTPException(status_code=400, detail="请提供文件名和行号")

    try:
        row_index = int(row_index)
    except ValueError:
        raise HTTPException(status_code=400, detail="行号必须是整数")

    try:
        result = excel_service.read_commands(file_name, row_index)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取 Excel 失败: {str(e)}")

    valid_rows = result.get("valid_rows", [])
    if row_index < 1 or row_index > len(valid_rows):
        raise HTTPException(status_code=400, detail="行号超出有效用例范围")

    return StreamingResponse(
        execute_asr_commands_stream(request, row_index, valid_rows),
        media_type="text/event-stream"
    )