"""ASR API 路由模块"""
import logging
import time
from datetime import datetime

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..services.asr_service import (
    AsrRuntimeError,
    BACKEND_KIND_COHERE,
    COHERE_DEFAULT_MODEL_NAME,
    COHERE_DEFAULT_REPO_ID,
    TextComparer,
    asr_service,
)
from ..services.excel_service import excel_service
from ..runtime import get_controller, get_current_device
from .execution import (
    ExecutionStopped,
    ensure_execution_active,
    format_sse,
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


def _plan_multi_tts_segments(commands: list[str]) -> list[dict]:
    """将命令按 TTS 标记切分为多个段。

    无 TTS 标记时返回单段（所有命令在录音中执行）。
    有 N 个 TTS 标记时返回 N 段，每段包含 trigger 命令和后续 post 命令。

    每段: {pre: [...], trigger: str, post: [...], uses_tts: bool}
    """
    tts_indexes = [i for i, cmd in enumerate(commands) if _is_tts_marker(cmd)]

    if not tts_indexes:
        # 无 TTS 标记：整条命令作为单段
        if len(commands) < 2:
            raise AsrRuntimeError("命令数量不足，至少需要 2 条命令")
        return [{"pre": commands[:-1], "trigger": commands[-1], "post": [], "uses_tts": False}]

    segments = []
    for i, tts_idx in enumerate(tts_indexes):
        if tts_idx >= len(commands) - 1:
            raise AsrRuntimeError(f"第 {i + 1} 个 TTS 标记后缺少待录音的命令")

        trigger = commands[tts_idx + 1]
        if _is_tts_marker(trigger):
            raise AsrRuntimeError(f"第 {i + 1} 个 TTS 标记后的命令不能继续是 TTS")

        # post: 当前 TTS 之后、下一个 TTS 之前的非 trigger 命令
        next_boundary = tts_indexes[i + 1] if i + 1 < len(tts_indexes) else len(commands)
        post = commands[tts_idx + 2:next_boundary]

        # pre: 仅第一段包含 TTS 之前的命令
        pre = commands[:tts_idx] if i == 0 else []

        segments.append({"pre": pre, "trigger": trigger, "post": post, "uses_tts": True})

    return segments


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
    """下载 Cohere Transcribe 模型到运行时目录（SSE 流式进度）。"""

    import asyncio
    import json
    import threading
    from queue import Queue, Empty

    progress_queue = Queue()

    def run_download():
        asr_service._download_with_progress(
            request.model_name, request.repo_id, BACKEND_KIND_COHERE, progress_queue
        )

    thread = threading.Thread(target=run_download, daemon=True)
    thread.start()

    async def event_generator():
        while True:
            try:
                event = progress_queue.get(timeout=0.5)
            except Empty:
                if not thread.is_alive():
                    break
                continue
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            if event.get("type") in ("done", "error"):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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


class SubstitutionsRequest(BaseModel):
    rules: dict[str, str]


@router.get("/substitutions")
async def get_substitutions():
    """获取当前 ASR 文本替换规则。"""
    return {"rules": TextComparer.get_substitutions()}


@router.put("/substitutions")
async def set_substitutions(request: SubstitutionsRequest):
    """保存 ASR 文本替换规则。"""
    try:
        TextComparer.save_substitutions(request.rules)
        return {"status": "ok", "rules": TextComparer.get_substitutions()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存替换规则失败: {str(e)}")


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

    # row_index 是 1-based 列表索引，直接用索引取行（不按 Excel 行号查找）
    executed_row = valid_rows[row_index - 1] if 1 <= row_index <= len(valid_rows) else {}
    case_title = executed_row.get("title") or f"第 {row_index} 行"
    commands = [command for command in executed_row.get("commands", []) if str(command or "").strip()]
    if not commands:
        yield format_sse({"status": "error", "message": "当前用例没有可执行命令"})
        return

    try:
        segments = _plan_multi_tts_segments(commands)
    except AsrRuntimeError as exc:
        yield format_sse({"status": "error", "message": str(exc)})
        return

    # 比对文本优先取 Excel M 列 TTSTXT，其次设备日志 TTS 输出
    reference_text = executed_row.get("tts_text", "") or ""
    total_segments = len(segments)

    try:
        await ensure_execution_active(request)
        yield format_sse({
            "status": "info",
            "message": f"已选择模型: {active_model['name']}"
        })
        yield format_sse({
            "status": "info",
            "message": f"开始执行 ASR 用例: {case_title} (共 {total_segments} 个校验段)"
        })

        if reference_text:
            yield format_sse({
                "status": "info",
                "message": f"已加载参考文本(Excel TTSTXT): {reference_text}"
            })
        else:
            yield format_sse({
                "status": "info",
                "message": "Excel 未填写 TTSTXT 参考文本，如捕获到 TTS 输出则将使用 TTS 文本进行比对",
            })
            logger.info(
                "ASR 参考文本为空(Excel TTSTXT 未填写): 用例 '%s'，改用 TTS 文本兜底",
                case_title,
            )

        # 逐段执行录音→TTS捕获→ASR→比对
        for seg_index, segment in enumerate(segments):
            recorder = None
            recording_started = False

            try:
                await ensure_execution_active(request)

                if total_segments > 1:
                    yield format_sse({
                        "status": "info",
                        "message": f"--- 校验段 {seg_index + 1}/{total_segments} ---",
                        "segment_index": seg_index,
                        "total_segments": total_segments,
                    })

                # 清空 logcat（在所有命令执行前清空，确保从 pre-commands 开始捕获 TTS 输出）
                controller = get_controller()
                controller.clear_logcat()

                # 执行 pre-commands（不录音，仅发送指令）
                pre_commands = segment.get("pre", [])
                if pre_commands:
                    async for event in stream_row_command_events([{"row": 1, "commands": pre_commands}], 1, request):
                        yield format_sse(event)

                # TTS 标记位置：开始录音
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
                logger.info("[ASR] 录音已启动: %s%s (段 %d/%d, TTS标记位置)", mode_label, device_info, seg_index + 1, total_segments)
                yield format_sse({
                    "status": "info",
                    "message": f"录制模式: {mode_label}{device_info}，遇到 TTS 标记，开始录音",
                    "segment_index": seg_index,
                })

                # 执行 trigger + post 命令
                record_commands = [segment["trigger"]] + segment.get("post", [])
                async for event in stream_row_command_events([{"row": 1, "commands": record_commands}], 1, request):
                    yield format_sse(event)

                # 等待 TTS 输出
                tts_log_path = str(
                    asr_service.log_root
                    / f"tts_{asr_service._sanitize_case_name(case_title)}_s{seg_index}_{datetime.now():%Y%m%d_%H%M%S}.log"
                )
                tts_text = ""
                for _tts_attempt in range(6):
                    await wait_with_cancellation(0.5, request)
                    tts_text = (controller.get_last_tts_text(log_path=tts_log_path) or "").strip()
                    if tts_text:
                        break

                if tts_text:
                    yield format_sse({
                        "status": "info",
                        "message": f"TTS 输出文本: {tts_text}",
                        "tts_text": tts_text,
                        "segment_index": seg_index,
                    })
                else:
                    yield format_sse({
                        "status": "info",
                        "message": "未捕获到 TTS 输出文本",
                        "tts_text": "",
                        "segment_index": seg_index,
                    })

                recorder.stop_recording()
                recording_started = False
                logger.info("[ASR] 录音已停止 (段 %d/%d)", seg_index + 1, total_segments)

                audio_path = asr_service.save_audio_recording(recorder, f"{case_title}_s{seg_index}")
                logger.info("[ASR] 录音已保存: %s", audio_path)
                yield format_sse({
                    "status": "info",
                    "message": f"录音已保存: {audio_path}",
                    "segment_index": seg_index,
                })

                # 确定比对文本：Excel TTSTXT 优先，其次 TTS 日志文本
                reference_path = "Excel TTSTXT" if reference_text else ""
                comparison_text = reference_text or tts_text
                comparison_source = "reference" if reference_text else "tts"

                if not comparison_text:
                    reference_root = asr_service.reference_root
                    reference_dir_exists = reference_root.exists() and reference_root.is_dir()
                    reference_file_count = len(list(reference_root.glob("*.txt"))) if reference_dir_exists else 0
                    normalized_key = asr_service._normalize_reference_key(case_title)

                    logger.warning(
                        "ASR NO_REF: 用例 '%s' 段 %d (normalized: '%s') 无参考文本且无 TTS 输出 | "
                        "TTS文本: '%s' | trigger='%s'",
                        case_title, seg_index + 1, normalized_key,
                        tts_text, segment["trigger"],
                    )

                    yield format_sse({
                        "status": "error",
                        "message": f"段 {seg_index + 1}: 未找到参考文本，且未捕获到 TTS 文本，无法完成比对",
                        "row_index": row_index,
                        "segment_index": seg_index,
                        "total_segments": total_segments,
                        "asr_result": "NO_REF",
                        "asr_score": None,
                        "transcribed_text": "",
                        "tts_text": tts_text,
                        "audio_path": str(audio_path),
                    })
                    continue

                if not reference_text:
                    yield format_sse({
                        "status": "info",
                        "message": "未找到参考文本，改用 TTS 输出文本进行比对",
                        "reference_text": comparison_text,
                        "tts_text": tts_text,
                        "comparison_source": comparison_source,
                        "segment_index": seg_index,
                    })

                # ── 音频处理（仅一次） ────────────────────────────────
                await ensure_execution_active(request)
                yield format_sse({
                    "status": "info",
                    "message": "正在音频处理...",
                    "segment_index": seg_index,
                })
                logger.info("[ASR] 开始音频处理: %s", audio_path)
                try:
                    # RMS 归一化到 -20dB，把采集卡等弱信号录音拉到标准音量，
                    # 避免 boost_volume 线性放大对 -60dB 级信号无济于事。
                    asr_service.enhance_audio(audio_path, target_db=-20.0)
                    logger.info("[ASR] enhance_audio 完成")
                except Exception as e:
                    logger.error("[ASR] enhance_audio 失败: %s", e, exc_info=True)
                try:
                    asr_service.reduce_noise(audio_path)
                    logger.info("[ASR] reduce_noise 完成")
                except Exception as e:
                    logger.error("[ASR] reduce_noise 失败: %s", e, exc_info=True)
                try:
                    asr_service.adjust_speed(audio_path, speed=0.9)
                    logger.info("[ASR] adjust_speed 完成")
                except Exception as e:
                    logger.error("[ASR] adjust_speed 失败: %s", e, exc_info=True)
                logger.info("[ASR] 音频处理全部完成")
                yield format_sse({
                    "status": "info",
                    "message": "音频处理完成，开始 ASR 识别...",
                    "segment_index": seg_index,
                })

                # ── 3 次 ASR 校验，取最优值 ────────────────────────────
                ASR_RETRY_COUNT = 3
                best_result = None
                best_score = -1.0
                comparison_threshold = TTS_COMPARISON_THRESHOLD if comparison_source == "tts" else 0.9

                for attempt in range(1, ASR_RETRY_COUNT + 1):
                    await ensure_execution_active(request)
                    yield format_sse({
                        "status": "info",
                        "message": f"--- 第 {attempt}/{ASR_RETRY_COUNT} 次校验 ---",
                        "segment_index": seg_index,
                    })

                    # ASR 识别
                    transcript = asr_service.transcribe_audio(audio_path)
                    # 应用文本替换规则
                    transcript_display = TextComparer.apply_substitutions(transcript) if transcript else transcript
                    transcript_path = asr_service.save_transcript(audio_path, transcript)
                    yield format_sse({
                        "status": "info",
                        "message": f"第 {attempt} 次校验：识别结果 = {transcript_display or '（空）'}",
                        "transcribed_text": transcript_display,
                        "transcript_path": str(transcript_path),
                        "tts_text": tts_text,
                        "segment_index": seg_index,
                    })

                    # 比对
                    comparison = asr_service.compare_transcript(transcript, comparison_text, threshold=comparison_threshold)
                    compare_report_path = asr_service.save_compare_report(
                        audio_path, transcript, comparison_text, comparison,
                    )
                    message = (
                        f"段 {seg_index + 1} 第 {attempt} 次: ASR 比对 {comparison['result']}: "
                        f"平均 {comparison['average'] * 100:.2f}% / "
                        f"余弦 {comparison['cosine'] * 100:.2f}% / 序列 {comparison['sequence'] * 100:.2f}%"
                    )

                    log_level = logging.INFO if comparison["matched"] else logging.WARNING
                    logger.log(
                        log_level,
                        "ASR %s: 用例 '%s' 段 %d 第 %d/%d 次 | source=%s | threshold=%.2f | "
                        "avg=%.4f cosine=%.4f sequence=%.4f | "
                        "transcript='%s' | comparison_text='%s'",
                        comparison["result"], case_title, seg_index + 1, attempt, ASR_RETRY_COUNT,
                        comparison_source, comparison_threshold,
                        comparison["average"], comparison["cosine"], comparison["sequence"],
                        transcript[:100], comparison_text[:100],
                    )
                    yield format_sse({
                        "status": "info",
                        "message": message,
                        "segment_index": seg_index,
                        "attempt": attempt,
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

                    # 更新最优结果
                    if comparison["average"] > best_score:
                        best_score = comparison["average"]
                        best_result = {
                            "attempt": attempt,
                            "transcript": transcript,
                            "transcript_path": transcript_path,
                            "comparison": comparison,
                            "compare_report_path": compare_report_path,
                        }

                    # 如果已经是满分，提前结束
                    if comparison["average"] >= 1.0:
                        logger.info("[ASR] 段 %d 第 %d 次已达到满分，提前结束重试", seg_index + 1, attempt)
                        break

                # 输出最终最优结果
                if best_result is None:
                    yield format_sse({
                        "status": "error",
                        "message": f"段 {seg_index + 1}: {ASR_RETRY_COUNT} 次校验均未产生有效结果",
                        "row_index": row_index,
                        "segment_index": seg_index,
                        "total_segments": total_segments,
                        "asr_result": "FAIL",
                        "asr_score": None,
                    })
                    continue

                best_comparison = best_result["comparison"]
                # 对最优结果的 transcript 应用文本替换
                best_transcript_display = TextComparer.apply_substitutions(best_result["transcript"]) if best_result["transcript"] else best_result["transcript"]
                logger.info(
                    "[ASR] 段 %d 最优结果: 第 %d 次 | avg=%.4f",
                    seg_index + 1, best_result["attempt"], best_comparison["average"],
                )
                yield format_sse({
                    "status": "success" if best_comparison["matched"] else "error",
                    "message": (
                        f"段 {seg_index + 1}: ASR 比对 {best_comparison['result']} "
                        f"(3 次中最优: 第 {best_result['attempt']} 次) — "
                        f"平均 {best_comparison['average'] * 100:.2f}% / "
                        f"余弦 {best_comparison['cosine'] * 100:.2f}% / "
                        f"序列 {best_comparison['sequence'] * 100:.2f}%"
                    ),
                    "row_index": row_index,
                    "segment_index": seg_index,
                    "total_segments": total_segments,
                    "asr_result": best_comparison["result"],
                    "asr_score": best_comparison["average"],
                    "asr_cosine": best_comparison["cosine"],
                    "asr_sequence": best_comparison["sequence"],
                    "transcribed_text": best_transcript_display,
                    "tts_text": tts_text,
                    "reference_text": comparison_text,
                    "reference_path": reference_path,
                    "comparison_source": comparison_source,
                    "audio_path": str(audio_path),
                    "transcript_path": str(best_result["transcript_path"]),
                    "compare_result_path": str(best_result["compare_report_path"]),
                })

            except ExecutionStopped:
                logger.warning("[ASR] 执行被用户停止 (段 %d/%d)", seg_index + 1, total_segments)
                if recorder is not None and recording_started:
                    recorder.stop_recording()
                return
            except AsrRuntimeError as exc:
                logger.error("[ASR] 运行时错误 (段 %d/%d): %s", seg_index + 1, total_segments, exc)
                if recorder is not None and recording_started:
                    recorder.stop_recording()
                yield format_sse({
                    "status": "error",
                    "message": f"段 {seg_index + 1}: {exc}",
                    "segment_index": seg_index,
                    "total_segments": total_segments,
                })
                continue
            except Exception as exc:
                logger.error("[ASR] 未知异常 (段 %d/%d): %s", seg_index + 1, total_segments, exc, exc_info=True)
                if recorder is not None and recording_started:
                    recorder.stop_recording()
                yield format_sse({
                    "status": "error",
                    "message": f"段 {seg_index + 1}: 执行 ASR 校验失败: {str(exc)}",
                    "segment_index": seg_index,
                    "total_segments": total_segments,
                })
                continue

    except ExecutionStopped:
        logger.warning("[ASR] 执行被用户停止")
        return
    except Exception as exc:
        logger.error("[ASR] 未知异常: %s", exc, exc_info=True)
        yield format_sse({
            "status": "error",
            "message": f"执行 ASR 用例失败: {str(exc)}",
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

