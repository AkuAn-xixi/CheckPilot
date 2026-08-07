"""FastAPI应用入口"""
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import os
import subprocess
import time
import threading
import math
import re
import json
import logging
from pathlib import Path
from .app.config import settings

# 日志配置：控制台 + 文件
if not logging.getLogger().handlers:
    from datetime import datetime
    _log_filename = datetime.now().strftime("AutoDeck_%Y%m%d_%H%M%S.log")
    _log_filepath = settings.LOG_DIR / _log_filename

    _file_handler = logging.FileHandler(str(_log_filepath), encoding="utf-8")
    _file_handler.setLevel(logging.INFO)
    _file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

    _console_handler = logging.StreamHandler()
    _console_handler.setLevel(logging.INFO)
    _console_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

    logging.basicConfig(level=logging.INFO, handlers=[_file_handler, _console_handler])

# 过滤 Windows Proactor 事件循环的连接重置噪音（播放/拖动录屏视频时浏览器
# Range 拉流被强制断开导致 asyncio 打 ERROR，实际不影响运行）。
class _AsyncioConnectionResetFilter(logging.Filter):
    def filter(self, record):
        if record.name == 'asyncio':
            message = record.getMessage()
            if '_call_connection_lost' in message or 'WinError 10054' in message or 'ConnectionResetError' in message:
                return False
        return True

logging.getLogger('asyncio').addFilter(_AsyncioConnectionResetFilter())
logger = logging.getLogger(__name__)
from .app.api import auth_router, asr_router, customization_router, devices_router, excel_router, execution_router, reports_router
from .app.utils.adb_controller import ADBController, KEYCODE_MAP, get_keycode_map
from .app.services.key_monitor_mapping_service import (
    KeyMonitorMappingError,
    KeyMonitorMappingService,
)
from .FieldValidation import get_valid_keys as get_runtime_valid_keys

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
    version=settings.VERSION
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(devices_router)
app.include_router(excel_router)
app.include_router(execution_router)
app.include_router(asr_router)
app.include_router(customization_router)
app.include_router(auth_router)
app.include_router(reports_router)

controller = ADBController()


def resolve_monitor_mapping_file() -> Path:
    candidates = [
        settings.WORKING_DIR / "monitor_key_mappings.json",
        settings.WORKING_DIR / "backend" / "monitor_key_mappings.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


MONITOR_MAPPING_FILE = resolve_monitor_mapping_file()
key_monitor_mapping_service = KeyMonitorMappingService(MONITOR_MAPPING_FILE)

current_device = None
monitor_active = False
monitor_stopping = False
monitor_live_sequence = ''
monitor_dataset_latest = ''
monitor_last_error = ''
monitor_last_error = ''
monitor_thread = None
last_key = None
last_key_time = 0
monitor_start_time = 0
monitor_device = ''
pressed_keys = {}
prev_key_name = None
prev_up_time = 0.0


class KeyMonitorMappingRequest(BaseModel):
    source_key: str
    target_key: str


class KeyMonitorSchemeCreateRequest(BaseModel):
    name: str


class KeyMonitorSchemeRenameRequest(BaseModel):
    new_name: str


class KeyMonitorSchemeDuplicateRequest(BaseModel):
    new_name: str


def _safe_frontend_path(relative_path: str) -> Path | None:
    frontend_dir = settings.FRONTEND_DIST_DIR
    if not frontend_dir.exists():
        return None

    candidate = (frontend_dir / relative_path).resolve(strict=False)
    frontend_root = frontend_dir.resolve(strict=False)
    try:
        candidate.relative_to(frontend_root)
    except ValueError:
        return None
    return candidate


def get_frontend_file(relative_path: str) -> Path | None:
    candidate = _safe_frontend_path(relative_path)
    if candidate is not None and candidate.exists() and candidate.is_file():
        return candidate
    return None


def get_frontend_index() -> Path | None:
    return get_frontend_file("index.html")

def format_monitor_sequence(sequence: str) -> str:
    """将内部换行分隔的监听序列格式化为前端使用的逗号分隔格式。"""
    if not sequence:
        return ''
    parts = [line.strip() for line in sequence.splitlines() if line.strip()]
    return ','.join(parts)


def normalize_monitor_key(key: str) -> str:
    return (key or '').strip().upper()


def get_monitor_valid_targets() -> list[str]:
    excluded = {"SRTTING", "PRIME_VII", "ACTIONS"}
    targets: set[str] = set()

    for key in get_keycode_map().keys():
        normalized = normalize_monitor_key(key)
        if normalized and normalized not in excluded:
            targets.add(normalized)

    try:
        for key in get_runtime_valid_keys():
            normalized = normalize_monitor_key(key)
            if normalized and normalized not in excluded:
                targets.add(normalized)
    except Exception:
        pass

    for target in key_monitor_mapping_service.all_known_targets():
        normalized = normalize_monitor_key(target)
        if normalized and normalized not in excluded:
            targets.add(normalized)

    logger.debug(f"[Monitor Valid Targets] 有效目标数量: {len(targets)}")
    return sorted(targets)


def replace_monitor_keys_in_sequence(sequence: str, replacements: dict[str, str]) -> str:
    if not sequence:
        return sequence
    lines = [line.strip() for line in sequence.splitlines() if line.strip()]
    rewritten = []
    for line in lines:
        parts = line.split('/')
        if len(parts) < 3:
            rewritten.append(line)
            continue
        source_key = normalize_monitor_key(parts[0])
        target_key = replacements.get(source_key, source_key)
        rewritten.append(f"{target_key}/{parts[1]}/{parts[2]}")
    return '\n'.join(rewritten) + ('\n' if rewritten else '')


MONITOR_USER_MAPPING = key_monitor_mapping_service.get_active_mapping()


def _refresh_active_user_mapping() -> dict[str, str]:
    """从 service 拉取当前激活方案的扁平视图，覆盖热路径用的全局变量。"""
    global MONITOR_USER_MAPPING
    MONITOR_USER_MAPPING = key_monitor_mapping_service.get_active_mapping()
    return MONITOR_USER_MAPPING

KEY_CUSTOM_MAPPING = {
    "00fc": "SOURCE",
    "TAB": "BACK",
    "ENTER": "OK",
    "0233": "APPS",
    "0234": "LIBRARY",
    "0235": "FILES",
    "SETUP": "SETTING",
    "CHANNELUP": "CHUP",
    "CHANNELDOWN": "CHDOWN",
    "1": "DIGITAL1",
    "2": "DIGITAL2",
    "3": "DIGITAL3",
    "4": "DIGITAL4",
    "5": "DIGITAL5",
    "6": "DIGITAL6",
    "7": "DIGITAL7",
    "8": "DIGITAL8",
    "9": "DIGITAL9",
    "0": "DIGITAL0",
    "F2": "NETFLIX",
    "F1": "YOUTUBE",
    "F4": "PRIME_VIDEO"
}


def resolve_monitored_key(raw_key: str) -> str:
    normalized_key = normalize_monitor_key(raw_key)
    if normalized_key in MONITOR_USER_MAPPING:
        return MONITOR_USER_MAPPING[normalized_key]
    mapped_key = KEY_CUSTOM_MAPPING.get(normalized_key, normalized_key)
    return MONITOR_USER_MAPPING.get(mapped_key, mapped_key)

def finalize_monitor_sequence(stop_time: float | None = None) -> str:
    """停止监听时回填最后一条指令的延迟。"""
    global monitor_live_sequence

    if not monitor_live_sequence:
        return monitor_live_sequence

    stop_ts = stop_time or time.time()
    lines = [line.strip() for line in monitor_live_sequence.splitlines() if line.strip()]
    if not lines:
        return monitor_live_sequence

    last_line = lines[-1]
    parts = last_line.split('/')
    if len(parts) >= 3 and parts[2] == '*':
        delay_for_last = max(0, math.ceil(stop_ts - last_key_time)) if last_key_time else 0
        lines[-1] = f"{parts[0]}/{parts[1]}/{delay_for_last}"
        monitor_live_sequence = '\n'.join(lines) + '\n'

    return monitor_live_sequence


def clear_monitor_sequences() -> None:
    global monitor_live_sequence, monitor_dataset_latest, monitor_last_error
    global last_key, last_key_time, monitor_start_time, monitor_device
    global pressed_keys, prev_key_name, prev_up_time

    monitor_live_sequence = ''
    monitor_dataset_latest = ''
    monitor_last_error = ''
    last_key = None
    last_key_time = 0
    monitor_start_time = 0
    monitor_device = ''
    pressed_keys = {}
    prev_key_name = None
    prev_up_time = 0.0


def update_current_monitor_sequences(source_key: str, target_key: str) -> None:
    global monitor_live_sequence, monitor_dataset_latest
    replacements = {source_key: target_key}
    monitor_live_sequence = replace_monitor_keys_in_sequence(monitor_live_sequence, replacements)
    monitor_dataset_latest = replace_monitor_keys_in_sequence(monitor_dataset_latest, replacements)

def start_key_monitor_th():
    global monitor_active, monitor_stopping, monitor_thread, monitor_live_sequence, monitor_dataset_latest, monitor_last_error, monitor_start_time, monitor_device, pressed_keys
    if monitor_active:
        monitor_active = False
        monitor_stopping = True
        if monitor_thread:
            monitor_thread.join(timeout=2)
        monitor_stopping = False
        monitor_dataset_latest = monitor_live_sequence
    else:
        monitor_active = True
        monitor_stopping = False
        clear_monitor_sequences()
        monitor_start_time = time.time()
        monitor_thread = threading.Thread(target=monitor_key_events, daemon=True)
        monitor_thread.start()

def monitor_key_events():
    global monitor_active, monitor_live_sequence, monitor_dataset_latest, monitor_last_error, monitor_start_time, last_key, last_key_time, monitor_device, pressed_keys, prev_key_name, prev_up_time
    device_arg = f"-s {current_device} " if current_device else ""
    cmd = f"adb {device_arg}shell getevent -lt -l"
    proc = None
    # 蓝牙 HID 遥控器的所有按键经常都被内核归到 KEY_UNKNOWN，需要用紧邻的
    # EV_MSC MSC_SCAN（HID Usage Code）来区分。这里维护"最近一次 SCAN 值"。
    pending_msc_scan: str | None = None
    try:
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def read_stderr():
            while monitor_active:
                err = proc.stderr.readline()
                if not err:
                    break
        threading.Thread(target=read_stderr, daemon=True).start()
        while monitor_active:
            line = proc.stdout.readline()
            if not line:
                break
            try:
                # 1) 先尝试抓 EV_MSC MSC_SCAN，缓存这条 SCAN 给紧随其后的 EV_KEY 用
                if "EV_MSC" in line and "MSC_SCAN" in line:
                    parts_msc = line.strip().split()
                    for i, part in enumerate(parts_msc):
                        if part == "MSC_SCAN" and i + 1 < len(parts_msc):
                            pending_msc_scan = parts_msc[i + 1]
                            break

                if "EV_KEY" in line:
                    if not monitor_device:
                        m = re.search(r"\]\s+([^\s:]+):", line)
                        if m:
                            monitor_device = m.group(1)
                    else:
                        m = re.search(r"\]\s+([^\s:]+):", line)
                        if m and m.group(1) != monitor_device:
                            continue
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        key_name = None
                        status = None
                        for i, part in enumerate(parts):
                            if part == "EV_KEY" and i + 2 < len(parts):
                                key_name = parts[i + 1]
                                status = parts[i + 2]
                                break
                        if key_name and status:
                            s = status.upper()
                            simplified_key = key_name.replace('KEY_', '')
                            # 蓝牙 HID 遥控器：很多按键被映射成 KEY_UNKNOWN / KEY_RESERVED，
                            # 这时 EV_KEY 完全无法区分按键，必须依赖 MSC_SCAN 兜底。
                            if simplified_key.upper() in {"UNKNOWN", "RESERVED", ""} and pending_msc_scan:
                                # 000c0085 → SCAN_C0085（去前导 0），保留唯一性 + 长度可控
                                scan_hex = pending_msc_scan.lstrip('0').upper() or '0'
                                simplified_key = f"SCAN_{scan_hex}"
                            # 用过的 SCAN 立即清掉，避免下次没 MSC_SCAN 的事件错用上一次值
                            pending_msc_scan = None
                            custom_key = resolve_monitored_key(simplified_key)
                            current_time = time.time()
                            if s in ('DOWN', '1'):
                                monitor_start_time = current_time
                                if pressed_keys.get(custom_key, False) and (current_time - last_key_time < 0.2):
                                    continue
                                if prev_key_name is not None:
                                    base_time = prev_up_time if prev_up_time > 0 else last_key_time
                                    delay_for_prev = max(0, math.ceil(current_time - base_time))
                                    if monitor_live_sequence:
                                        lines = monitor_live_sequence.strip().split('\n')
                                    else:
                                        lines = []
                                    if lines:
                                        last_line = lines[-1]
                                        if last_line.startswith(prev_key_name + '/'):
                                            parts_prev = last_line.split('/')
                                            if len(parts_prev) >= 3:
                                                prev_count = int(parts_prev[1])
                                                prev_delay_token = parts_prev[2]
                                                if prev_delay_token == '*' or prev_delay_token == '0':
                                                    lines[-1] = f"{prev_key_name}/{prev_count}/{delay_for_prev}"
                                    monitor_live_sequence = '\n'.join(lines) + ('\n' if lines else '')
                                monitor_live_sequence += f"{custom_key}/1/*\n"
                                pressed_keys[custom_key] = True
                                last_key = custom_key
                                last_key_time = current_time
                                prev_key_name = custom_key
                            elif s in ('UP', '0'):
                                pressed_keys[custom_key] = False
                                if prev_key_name == custom_key:
                                    prev_up_time = current_time
                                if len(monitor_live_sequence) > 1000:
                                    monitor_live_sequence = monitor_live_sequence[-1000:]
            except Exception as e:
                monitor_last_error = str(e)
    except Exception as e:
        monitor_last_error = f"{e}"
    finally:
        finalize_monitor_sequence()
        monitor_dataset_latest = monitor_live_sequence
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=1)
            except Exception:
                pass
        monitor_active = False

@app.get("/")
async def root():
    """根路径"""
    frontend_index = get_frontend_index()
    if frontend_index is not None:
        return FileResponse(frontend_index)
    return {"message": "ADB Control API", "version": settings.VERSION}

@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}

def _clear_screenshots_sync() -> dict:
    """同步清除所有截图（IO 密集，放到线程池执行以避免阻塞事件循环）。"""
    count = 0
    screenshot_dir = settings.SCREENSHOT_DIR
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    for file in os.listdir(screenshot_dir):
        if file.endswith('.png') and (file.startswith('screenshot_') or file.startswith('UC_') or
                                       file.startswith('HOME') or file.startswith('UserCenter')):
            try:
                os.remove(screenshot_dir / file)
                count += 1
            except Exception:
                pass
    return {"status": "ok", "deleted_count": count}


@app.post("/api/screenshot/clear")
async def clear_screenshots():
    """清除所有截图"""
    try:
        return await asyncio.to_thread(_clear_screenshots_sync)
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/screenshot/{filename}")
async def get_screenshot(filename: str):
    """获取截图"""
    file_path = settings.SCREENSHOT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="截图不存在")
    return FileResponse(file_path)

@app.get("/api/recording/{filename}")
async def get_recording(filename: str):
    """获取录屏视频"""
    file_path = settings.RECORDING_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="录屏文件不存在")
    # 根据文件扩展名返回正确的 MIME 类型
    if filename.endswith('.avi'):
        return FileResponse(file_path, media_type="video/x-msvideo")
    elif filename.endswith('.webm'):
        return FileResponse(file_path, media_type="video/webm")
    return FileResponse(file_path, media_type="video/mp4")


@app.post("/api/recording/{filename}/open-local")
async def open_recording_local(filename: str):
    """使用本地播放器打开录屏文件"""
    import subprocess
    import os
    file_path = settings.RECORDING_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="录屏文件不存在")

    abs_path = str(file_path.resolve())
    try:
        if os.name == 'nt':  # Windows
            os.startfile(abs_path)
        elif os.name == 'posix':  # macOS / Linux
            subprocess.Popen(['xdg-open', abs_path])
        return {"success": True, "path": abs_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"打开文件失败: {str(e)}")


@app.get("/api/recording/{filename}/path")
async def get_recording_path(filename: str):
    """获取录屏文件的本地路径"""
    file_path = settings.RECORDING_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="录屏文件不存在")
    return {"path": str(file_path.resolve())}

@app.get("/api/monitor/status")
async def get_monitor_status():
    """获取监视器状态"""
    formatted_live = format_monitor_sequence(monitor_live_sequence)
    formatted_latest = format_monitor_sequence(monitor_dataset_latest)
    return {
        "active": monitor_active,
        "sequence": formatted_live if monitor_active else formatted_latest,
        "live_sequence": formatted_live,
        "latest_sequence": formatted_latest,
        "last_error": monitor_last_error
    }

@app.post("/api/monitor/start")
async def start_monitor():
    """启动按键监视"""
    start_key_monitor_th()
    return {"status": "started"}

@app.post("/api/monitor/stop")
async def stop_monitor():
    """停止按键监视"""
    global monitor_active, monitor_stopping, monitor_thread, monitor_dataset_latest
    finalize_monitor_sequence()
    monitor_dataset_latest = monitor_live_sequence
    monitor_active = False
    monitor_stopping = True
    if monitor_thread and monitor_thread.is_alive():
        try:
            monitor_thread.join(timeout=2)
        except Exception:
            pass
    monitor_stopping = False
    return {"status": "stopped", "sequence": format_monitor_sequence(monitor_dataset_latest)}


@app.post("/api/monitor/clear")
async def clear_monitor():
    """清空最近一次监听结果。"""
    if monitor_active:
        raise HTTPException(status_code=409, detail="监听进行中，无法清空结果")

    clear_monitor_sequences()
    return {"status": "cleared"}

@app.get("/api/keymonitor/status")
async def get_keymonitor_status():
    """兼容旧前端的按键监听状态接口。"""
    return await get_monitor_status()

@app.post("/api/keymonitor/start")
async def start_keymonitor():
    """兼容旧前端的启动按键监听接口。"""
    return await start_monitor()

@app.post("/api/keymonitor/stop")
async def stop_keymonitor():
    """兼容旧前端的停止按键监听接口。"""
    return await stop_monitor()


@app.post("/api/keymonitor/clear")
async def clear_keymonitor():
    """兼容旧前端的清空按键监听结果接口。"""
    return await clear_monitor()


@app.get("/api/keymonitor/mappings")
async def get_keymonitor_mappings():
    """返回当前激活方案的纠错规则、所有可选的修正目标按键。"""
    mapping = key_monitor_mapping_service.get_active_mapping()
    _refresh_active_user_mapping()
    schemes_view = key_monitor_mapping_service.list_schemes()
    return {
        "mappings": dict(sorted(mapping.items())),
        "valid_targets": get_monitor_valid_targets(),
        "active_scheme": schemes_view["active_scheme"],
        "schemes": schemes_view["schemes"],
    }


@app.post("/api/keymonitor/mappings")
async def save_keymonitor_mapping(payload: KeyMonitorMappingRequest):
    try:
        updated_mapping = key_monitor_mapping_service.upsert_mapping(
            payload.source_key,
            payload.target_key,
        )
    except KeyMonitorMappingError as exc:
        return {"success": False, "message": str(exc)}

    source_key = normalize_monitor_key(payload.source_key)
    target_key = normalize_monitor_key(payload.target_key)
    _refresh_active_user_mapping()
    update_current_monitor_sequences(source_key, target_key)
    schemes_view = key_monitor_mapping_service.list_schemes()
    return {
        "success": True,
        "mappings": dict(sorted(updated_mapping.items())),
        "valid_targets": get_monitor_valid_targets(),
        "active_scheme": schemes_view["active_scheme"],
        "schemes": schemes_view["schemes"],
        "latest_sequence": format_monitor_sequence(monitor_dataset_latest),
        "live_sequence": format_monitor_sequence(monitor_live_sequence)
    }


@app.delete("/api/keymonitor/mappings/{source_key}")
async def delete_keymonitor_mapping(source_key: str):
    try:
        updated_mapping = key_monitor_mapping_service.delete_mapping(source_key)
    except KeyMonitorMappingError as exc:
        return {"success": False, "message": str(exc)}

    _refresh_active_user_mapping()
    schemes_view = key_monitor_mapping_service.list_schemes()
    return {
        "success": True,
        "mappings": dict(sorted(updated_mapping.items())),
        "active_scheme": schemes_view["active_scheme"],
        "schemes": schemes_view["schemes"],
    }


# ───────────────────── 纠错规则方案管理 ─────────────────────

def _build_scheme_response(extra: dict | None = None) -> dict:
    """统一格式：返回方案视图 + 当前激活方案的扁平映射 + valid_targets。"""
    schemes_view = key_monitor_mapping_service.list_schemes()
    payload = {
        "success": True,
        "active_scheme": schemes_view["active_scheme"],
        "schemes": schemes_view["schemes"],
        "mappings": dict(sorted(key_monitor_mapping_service.get_active_mapping().items())),
        "valid_targets": get_monitor_valid_targets(),
    }
    if extra:
        payload.update(extra)
    return payload


@app.get("/api/keymonitor/mapping-schemes")
async def list_keymonitor_mapping_schemes():
    return _build_scheme_response()


@app.post("/api/keymonitor/mapping-schemes")
async def create_keymonitor_mapping_scheme(payload: KeyMonitorSchemeCreateRequest):
    try:
        key_monitor_mapping_service.create_scheme(payload.name)
    except KeyMonitorMappingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    _refresh_active_user_mapping()
    return _build_scheme_response({"created": payload.name.strip()})


@app.put("/api/keymonitor/mapping-schemes/{scheme_name}/activate")
async def activate_keymonitor_mapping_scheme(scheme_name: str):
    try:
        key_monitor_mapping_service.activate_scheme(scheme_name)
    except KeyMonitorMappingError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    _refresh_active_user_mapping()
    return _build_scheme_response({"activated": scheme_name})


@app.put("/api/keymonitor/mapping-schemes/{scheme_name}")
async def rename_keymonitor_mapping_scheme(scheme_name: str, payload: KeyMonitorSchemeRenameRequest):
    try:
        key_monitor_mapping_service.rename_scheme(scheme_name, payload.new_name)
    except KeyMonitorMappingError as exc:
        status_code = 400 if "已存在" in str(exc) or "不能" in str(exc) else 404
        raise HTTPException(status_code=status_code, detail=str(exc))
    _refresh_active_user_mapping()
    return _build_scheme_response({"renamed": payload.new_name.strip()})


@app.post("/api/keymonitor/mapping-schemes/{scheme_name}/duplicate")
async def duplicate_keymonitor_mapping_scheme(scheme_name: str, payload: KeyMonitorSchemeDuplicateRequest):
    try:
        key_monitor_mapping_service.duplicate_scheme(scheme_name, payload.new_name)
    except KeyMonitorMappingError as exc:
        status_code = 400 if "已存在" in str(exc) or "不能" in str(exc) else 404
        raise HTTPException(status_code=status_code, detail=str(exc))
    _refresh_active_user_mapping()
    return _build_scheme_response({"duplicated": payload.new_name.strip()})


@app.delete("/api/keymonitor/mapping-schemes/{scheme_name}")
async def delete_keymonitor_mapping_scheme(scheme_name: str):
    try:
        key_monitor_mapping_service.delete_scheme(scheme_name)
    except KeyMonitorMappingError as exc:
        status_code = 400 if "至少" in str(exc) else 404
        raise HTTPException(status_code=status_code, detail=str(exc))
    _refresh_active_user_mapping()
    return _build_scheme_response({"deleted": scheme_name})


def _safe_export_filename(stem: str) -> str:
    safe_stem = re.sub(r"[\\/:*?\"<>|]+", "_", str(stem or "").strip()) or "key-monitor-schemes"
    return f"{safe_stem}.json"


def _build_attachment_disposition(filename: str) -> str:
    """构造 ``Content-Disposition`` 头，让中文文件名也能在 latin-1 限制下安全传输。

    HTTP 头默认只允许 latin-1。直接把"默认.json"这种中文塞进
    ``filename="..."`` 会触发 ``UnicodeEncodeError``。RFC 5987 规定用
    ``filename*=UTF-8''<percent-encoded>`` 表示非 ASCII 文件名，主流浏览器
    都支持；同时保留一个 ASCII 兜底的 ``filename=`` 给极老的客户端。
    """
    from urllib.parse import quote

    # ASCII 兜底名：把所有非 ASCII 字符替换成 ``_``，避免 latin-1 编码失败
    ascii_fallback = "".join(ch if ord(ch) < 128 else "_" for ch in filename)
    if not ascii_fallback or ascii_fallback in {"_", ".", ""}:
        ascii_fallback = "key-monitor-schemes.json"
    encoded = quote(filename, safe="")
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded}"


@app.get("/api/keymonitor/mapping-schemes/{scheme_name}/export")
async def export_keymonitor_mapping_scheme(scheme_name: str):
    """导出单个方案为 JSON 下载。"""
    try:
        payload = key_monitor_mapping_service.export_scheme(scheme_name)
    except KeyMonitorMappingError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    filename = _safe_export_filename(f"key-monitor-{scheme_name}")
    return JSONResponse(
        content=payload,
        headers={
            "Content-Disposition": _build_attachment_disposition(filename),
        },
    )


@app.get("/api/keymonitor/mapping-schemes/export-all")
async def export_all_keymonitor_mapping_schemes():
    """导出全部方案为 JSON 下载。"""
    payload = key_monitor_mapping_service.export_all_schemes()
    filename = _safe_export_filename("key-monitor-all-schemes")
    return JSONResponse(
        content=payload,
        headers={
            "Content-Disposition": _build_attachment_disposition(filename),
        },
    )


@app.post("/api/keymonitor/mapping-schemes/import")
async def import_keymonitor_mapping_schemes(
    file: UploadFile = File(...),
    conflict: str = Form("rename"),
    scheme_name: str | None = Form(default=None),
):
    """导入一个或多个方案。

    - ``file``: 之前由本接口导出的 JSON，或扁平 ``{KEY: KEY}`` JSON
    - ``conflict``: ``rename`` / ``overwrite`` / ``skip``
    - ``scheme_name``: 可选；扁平格式必须给；完整格式且只有一个方案时也可临时改名
    """
    try:
        raw_bytes = await file.read()
    finally:
        await file.close()

    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="导入文件不是合法的 UTF-8 文本") from exc

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"导入文件不是合法 JSON: {exc.msg}") from exc

    try:
        result = key_monitor_mapping_service.import_schemes(
            payload,
            conflict=conflict,
            scheme_name_override=(scheme_name or None),
        )
    except KeyMonitorMappingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    _refresh_active_user_mapping()
    return _build_scheme_response({
        "imported": result["imported"],
        "renamed": result["renamed"],
        "skipped": result["skipped"],
    })

if settings.SCREENSHOT_DIR.exists():
    app.mount("/screenshots", StaticFiles(directory=settings.SCREENSHOT_DIR), name="screenshots")

if settings.RECORDING_DIR.exists():
    app.mount("/recordings", StaticFiles(directory=settings.RECORDING_DIR), name="recordings")

if settings.REPORTS_DIR.exists():
    app.mount("/report-files", StaticFiles(directory=settings.REPORTS_DIR), name="report-files")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str):
    if full_path.startswith("api/") or full_path == "api":
        raise HTTPException(status_code=404, detail="Not Found")

    frontend_file = get_frontend_file(full_path)
    if frontend_file is not None:
        return FileResponse(frontend_file)

    frontend_index = get_frontend_index()
    if frontend_index is not None:
        return FileResponse(frontend_index)

    raise HTTPException(status_code=404, detail="Not Found")
