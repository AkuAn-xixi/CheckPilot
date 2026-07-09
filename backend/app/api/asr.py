"""ASR API 路由模块"""
import logging
import time

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..services.asr_service import (
    AsrRuntimeError,
    COHERE_DEFAULT_MODEL_NAME,
    COHERE_DEFAULT_REPO_ID,
    asr_service,
)
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/excel/asr", tags=["asr"])
TTS_MARKER = "TTS"
TTS_COMPARISON_THRESHOLD = 0.85


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


class CohereTranscribeDownloadRequest(BaseModel):
    model_name: str = COHERE_DEFAULT_MODEL_NAME
    repo_id: str = COHERE_DEFAULT_REPO_ID


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


@router.post("/models/download")
async def download_asr_model(request: CohereTranscribeDownloadRequest):
    """下载 Cohere Transcribe 模型到运行时目录。

    与"导入本地模型目录"互补：用户可以选择直接通过 HuggingFace 镜像拉取
    ``CohereLabs/cohere-transcribe-03-2026`` 的全部权重，免去手工选择
    几十个文件再批量上传。
    """

    try:
        return asr_service.download_cohere_transcribe(request.model_name, request.repo_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AsrRuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载模型失败: {str(e)}")


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


class AudioConfigRequest(BaseModel):
    audio_input_mode: str = "speaker"
    audio_device_index: int | None = None


@router.get("/audio-devices")
async def list_audio_devices():
    """列出系统所有音频输入设备，供用户选择采集卡或麦克风。"""
    try:
        devices = asr_service.list_audio_devices()
        return {"devices": devices}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取音频设备列表失败: {str(e)}")


@router.get("/audio-config")
async def get_audio_config():
    """获取当前 ASR 音频输入配置。"""
    return asr_service.get_audio_config()


@router.put("/audio-config")
async def set_audio_config(request: AudioConfigRequest):
    """保存 ASR 音频输入配置。"""
    try:
        return asr_service.set_audio_config(request.audio_input_mode, request.audio_device_index)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存音频配置失败: {str(e)}")


async def execute_asr_commands_stream(request: Request, file_name: str, row_index: int, valid_rows: list):
    execution_started_at = int(time.time() * 1000)
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
            # 记录参考文件搜索细节，帮助排查匹配失败
            ref_root = asr_service.reference_root
            ref_dir_ok = ref_root.exists() and ref_root.is_dir()
            ref_files = [f.stem for f in ref_root.glob("*.txt")] if ref_dir_ok else []
            normalized_key = asr_service._normalize_reference_key(case_title)
            yield format_sse({
                "status": "info",
                "message": (
                    f"未找到用例 '{case_title}' 的参考文本 (normalized: '{normalized_key}')，"
                    f"参考目录: {ref_root} (存在={ref_dir_ok}, 文件数={len(ref_files)})，"
                    f"如捕获到 TTS 输出则将使用 TTS 文本进行比对"
                ),
                "diagnostic": {
                    "case_title": case_title,
                    "normalized_key": normalized_key,
                    "reference_root": str(ref_root),
                    "reference_dir_exists": ref_dir_ok,
                    "reference_file_count": len(ref_files),
                },
            })
            logger.info(
                "ASR 参考文本未匹配: 用例 '%s' (normalized: '%s') | 参考目录: %s (exists=%s, txt_count=%d)",
                case_title, normalized_key, ref_root, ref_dir_ok, len(ref_files),
            )

        # 有 TTS 标记：先执行标记前的命令（不录音），标记处开始录音
        # 无 TTS 标记：所有命令都录音
        if uses_tts_marker and pre_record_commands:
            async for event in stream_row_command_events([{"commands": pre_record_commands}], 1, request):
                yield format_sse(event)

        # 开始录音
        await ensure_execution_active(request)
        audio_config = asr_service.get_audio_config()
        audio_device_index = audio_config.get("audio_device_index")
        recorder = asr_service.create_recorder(device=audio_device_index)

        try:
            recorder.start_recording()
        except Exception as rec_exc:
            logger.error("[ASR] start_recording 失败: %s", rec_exc)
            raise

        recording_started = True
        mode_label = "采集卡" if audio_config.get("audio_input_mode") == "capture_card" else "外放"
        device_info = f" (设备#{audio_device_index})" if audio_device_index is not None else " (系统默认)"
        logger.info("[ASR] 录音已启动: %s%s", mode_label, device_info)
        yield format_sse({
            "status": "info",
            "message": f"录制模式: {mode_label}{device_info}，开始录音"
        })

        # 清空 logcat，执行需要录音的命令
        controller = get_controller()
        controller.clear_logcat()

        if uses_tts_marker:
            record_commands = [recorded_command] + post_record_commands
        else:
            record_commands = commands

        async for event in stream_row_command_events([{"commands": record_commands}], 1, request):
            yield format_sse(event)

        # 等待 TTS 输出完成后停止录音
        await wait_with_cancellation(0.5, request)

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
        logger.info("[ASR] 录音已停止")

        audio_path = asr_service.save_audio_recording(recorder, case_title)
        logger.info("[ASR] 录音已保存: %s", audio_path)
        yield format_sse({
            "status": "info",
            "message": f"录音已保存: {audio_path}"
        })

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
            # 收集诊断信息，帮助定位 NO_REF 根因
            reference_root = asr_service.reference_root
            reference_dir_exists = reference_root.exists() and reference_root.is_dir()
            reference_file_count = len(list(reference_root.glob("*.txt"))) if reference_dir_exists else 0
            normalized_key = asr_service._normalize_reference_key(case_title)

            # 检查是否有近似匹配的参考文件（辅助排查命名不一致问题）
            similar_refs = []
            if reference_dir_exists:
                for ref_file in reference_root.glob("*.txt"):
                    ref_stem = ref_file.stem
                    similar_refs.append(ref_stem)

            diagnostic = {
                "case_title": case_title,
                "normalized_key": normalized_key,
                "reference_root": str(reference_root),
                "reference_dir_exists": reference_dir_exists,
                "reference_file_count": reference_file_count,
                "available_references": similar_refs[:20],  # 最多展示 20 个，避免过多
                "tts_capture_attempted": True,
                "tts_raw": tts_text,
                "uses_tts_marker": uses_tts_marker,
                "recorded_command": recorded_command,
            }

            logger.warning(
                "ASR NO_REF: 用例 '%s' (normalized: '%s') 无参考文本且无 TTS 输出 | "
                "参考目录: %s (exists=%s, txt_count=%d) | "
                "TTS文本: '%s' | uses_tts_marker=%s | recorded_cmd='%s'",
                case_title, normalized_key,
                reference_root, reference_dir_exists, reference_file_count,
                tts_text, uses_tts_marker, recorded_command,
            )

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
                "diagnostic": diagnostic,
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

        comparison_threshold = TTS_COMPARISON_THRESHOLD if comparison_source == "tts" else 0.9
        comparison = asr_service.compare_transcript(transcript, comparison_text, threshold=comparison_threshold)
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

        log_level = logging.INFO if comparison["matched"] else logging.WARNING
        logger.log(
            log_level,
            "ASR %s: 用例 '%s' | source=%s | threshold=%.2f | "
            "avg=%.4f cosine=%.4f sequence=%.4f | "
            "transcript='%s' | comparison_text='%s'",
            comparison["result"], case_title, comparison_source, comparison_threshold,
            comparison["average"], comparison["cosine"], comparison["sequence"],
            transcript[:100], comparison_text[:100],
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
        logger.warning("[ASR] 执行被用户停止")
        if recorder is not None and recording_started:
            recorder.stop_recording()
        return
    except AsrRuntimeError as exc:
        logger.error("[ASR] 运行时错误: %s", exc)
        if recorder is not None and recording_started:
            recorder.stop_recording()
        yield format_sse({
            "status": "error",
            "message": str(exc),
        })
    except Exception as exc:
        logger.error("[ASR] 未知异常: %s", exc, exc_info=True)
        if recorder is not None and recording_started:
            recorder.stop_recording()
        message = f"执行 ASR 用例失败: {str(exc)}"
        yield format_sse({
            "status": "error",
            "message": message,
        })


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
        execute_asr_commands_stream(request, file_name, row_index, valid_rows),
        media_type="text/event-stream"
    )

