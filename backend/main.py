"""FastAPI应用入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import subprocess
import time
import threading
import math
import re

from app.config import settings
from app.api import devices_router, excel_router, execution_router
from app.utils.adb_controller import ADBController

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

controller = ADBController()

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

KEY_CUSTOM_MAPPING = {
    "00fc": "SOURCE",
    "TAB": "BACK",
    "ENTER": "OK",
    "0233": "APPS",
    "0234": "LIBRARY",
    "0235": "FILES",
    "SETUP": "SRTTING",
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
        monitor_live_sequence = ''
        monitor_last_error = ''
        monitor_start_time = time.time()
        monitor_device = ''
        pressed_keys = {}
        monitor_thread = threading.Thread(target=monitor_key_events, daemon=True)
        monitor_thread.start()

def monitor_key_events():
    global monitor_active, monitor_live_sequence, monitor_last_error, monitor_start_time, last_key, last_key_time, monitor_device, pressed_keys, prev_key_name, prev_up_time
    device_arg = f"-s {current_device} " if current_device else ""
    cmd = f"adb {device_arg}shell getevent -lt -l"
    proc = None
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
                            custom_key = KEY_CUSTOM_MAPPING.get(simplified_key, simplified_key)
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
    return {"message": "ADB Control API", "version": settings.VERSION}

@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}

@app.post("/api/screenshot/clear")
async def clear_screenshots():
    """清除所有截图"""
    try:
        count = 0
        for file in os.listdir('.'):
            if file.endswith('.png') and (file.startswith('screenshot_') or file.startswith('UC_') or
                                           file.startswith('HOME') or file.startswith('UserCenter')):
                try:
                    os.remove(file)
                    count += 1
                except Exception:
                    pass
        return {"status": "ok", "deleted_count": count}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/screenshot/{filename}")
async def get_screenshot(filename: str):
    """获取截图"""
    file_path = os.path.join(os.getcwd(), filename)
    if not os.path.exists(file_path):
        return {"error": "截图不存在"}
    return FileResponse(file_path)

@app.get("/api/monitor/status")
async def get_monitor_status():
    """获取监视器状态"""
    return {
        "active": monitor_active,
        "sequence": monitor_live_sequence,
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
    global monitor_active
    monitor_active = False
    return {"status": "stopped", "sequence": monitor_dataset_latest}

if os.path.exists("screenshots"):
    app.mount("/screenshots", StaticFiles(directory="screenshots"), name="screenshots")
