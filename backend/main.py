from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import subprocess
import time
import pandas as pd
import os
import threading
import math
import re
import sys

# 定义请求模型
class DeviceSelectRequest(BaseModel):
    device_index: int

class CommandExecuteRequest(BaseModel):
    commands: str

class SingleCommandExecuteRequest(BaseModel):
    command: str

class ExcelExecuteRequest(BaseModel):
    file_name: str
    row_index: int
class AppendSequenceRequest(BaseModel):
    file_name: str
    sequence: str
class WriteCellRequest(BaseModel):
    file_name: str
    column_name: str
    row_index: int
    value: str

app = FastAPI(
    title="ADB Control API",
    description="ADB设备控制和命令执行API",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Keycode 映射表
KEYCODE_MAP = {
    "OK": 23,  # ENTER 键
    "HOME": 3,
    "BACK": 4,
    "UP": 19,  # KEYCODE_DPAD_UP
    "DOWN": 20,  # KEYCODE_DPAD_DOWN
    "LEFT": 21,  # KEYCODE_DPAD_LEFT
    "RIGHT": 22,  # KEYCODE_DPAD_RIGHT
    "MENU": 82,
    "SETTING": 176,
    "DIGITAL0": 7,
    "DIGITAL1": 8,
    "DIGITAL2": 9,
    "DIGITAL3": 10,
    "DIGITAL4": 11,
    "DIGITAL5": 12,
    "DIGITAL6": 13,
    "DIGITAL7": 14,
    "DIGITAL8": 15,
    "DIGITAL9": 16,
    "APPS": 360,
    # 新增按键
    "POWER": 26,
    "SOURCE": 178,
    "CHUP": 82,
    "CHDOWN": 166,
    "EXIT": 167,
    "LIBRARY": 358,
    "TV_AV": 24,
    "VOLUMEUP": 24,
    "VOLUMEDOWN": 25,
    "NETFLIX": 132,
    "YOUTUBE": 131,
    "PRIME_VII": 134,
    "ACTIONS": 222,
    "FILES": 359,
    "RED": 1,
    "GREEN": 2,
    "YELLOW": 3,
    "BLUE": 4,
    "INFORMATION": 7,
    "MUTE": 164
}

# 全局变量
current_device = None
monitor_active = False
monitor_stopping = False
monitor_live_sequence = ''
monitor_dataset_latest = ''
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
                                # 去抖：同键短时间重复DOWN忽略
                                if pressed_keys.get(custom_key, False) and (current_time - last_key_time < 0.2):
                                    continue
                                # 在新按键开始时，回填上一键的延迟（上一次UP到这次DOWN）
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

class ADBController:
    def __init__(self):
        self.device_serial = None

    def list_devices(self):
        """列出所有连接的ADB设备"""
        try:
            result = subprocess.run("adb devices", shell=True, check=True, capture_output=True, text=True)
            lines = result.stdout.splitlines()
            devices = []

            for line in lines[1:]:  # 跳过第一行标题
                if line.strip() and "device" in line:
                    serial = line.split('\t')[0]
                    devices.append(serial)

            return devices
        except subprocess.CalledProcessError as e:
            print(f"获取设备列表失败: {e}")
            return []

    def select_device(self, device_serial):
        """选择要连接的ADB设备"""
        self.device_serial = device_serial
        return True

    def send_keyevent(self, keycode, keyname, delay=0):
        """发送ADB keyevent并可选延迟"""
        if not 1 <= keycode <= 999:
            raise ValueError("Keycode must be between 1 and 999")

        # 添加设备序列号参数
        device_arg = f"-s {self.device_serial} " if self.device_serial else ""
        command = f"adb {device_arg}shell input keyevent {keycode}"

        try:
            subprocess.run(command, shell=True, check=True)
            print(f"已发送: {keyname}")
            if delay > 0:
                time.sleep(delay)
            return True
        except subprocess.CalledProcessError as e:
            print(f"发送 {keyname} ({keycode}) 失败: {e}")
            return False

    def execute_commands(self, command_sequence):
        """执行多条ADB命令"""
        commands = command_sequence.split(',')
        results = []
        
        for cmd in commands:
            try:
                parts = cmd.strip().split('/')
                if len(parts) != 3:
                    results.append({"status": "error", "message": f"命令格式错误: {cmd}"})
                    continue
                
                keyname, repeat, delay = parts
                keyname = keyname.upper()
                repeat = int(repeat)
                delay = float(delay)
                
                if keyname not in KEYCODE_MAP:
                    results.append({"status": "error", "message": f"未知按键: {keyname}"})
                    continue
                
                keycode = KEYCODE_MAP[keyname]
                for _ in range(repeat):
                    success = self.send_keyevent(keycode, keyname, delay)
                    if success:
                        results.append({"status": "success", "message": f"已发送: {keyname}"})
                    else:
                        results.append({"status": "error", "message": f"发送失败: {keyname}"})
                        break
            except ValueError as e:
                results.append({"status": "error", "message": f"命令执行错误: {e}"})
        
        return results
    
    def take_screenshot(self, title=None):
        """使用ADB截图（更稳健，支持/data/local/tmp，带重试）"""
        device_arg = f"-s {self.device_serial} " if self.device_serial else ""
        if title:
            # 使用用例标题作为文件名，移除可能的非法字符
            safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)
            local_path = f"{safe_title}.png"
        else:
            ts = int(time.time() * 1000)
            local_path = f"screenshot_{ts}.png"
        remote_candidates = [
            f"/data/local/tmp/{os.path.basename(local_path)}",
            f"/sdcard/{os.path.basename(local_path)}",
        ]
        for remote_path in remote_candidates:
            try:
                cmd_cap = f"adb {device_arg}shell screencap -p {remote_path}"
                subprocess.run(cmd_cap, shell=True, check=True)
                time.sleep(0.1)
                cmd_pull = f"adb {device_arg}pull {remote_path} {local_path}"
                subprocess.run(cmd_pull, shell=True, check=True)
                # 尝试删除远端文件（忽略失败）
                try:
                    subprocess.run(f"adb {device_arg}shell rm {remote_path}", shell=True)
                except Exception:
                    pass
                # 不再限制留存图片数量
                # 移除了自动清理旧截图的逻辑，所有截图都会被保留
                print(f"截图成功，保存到: {local_path}")
                return local_path
            except subprocess.CalledProcessError as e:
                print(f"截图失败（尝试 {remote_path}）: {e}")
                time.sleep(0.2)
                continue
        return None

    def read_excel_commands(self, excel_path, target_row=None):
        """读取Excel文件中的命令"""
        try:
            # 读取Excel文件
            df = pd.read_excel(excel_path)
            
            # 构建命令序列
            commands = []
            valid_rows = []
            skipped_rows = []
            
            # 检查是否是SmartTV模板格式
            if 'preScript' in df.columns:
                print("检测到SmartTV模板格式，正在解析preScript列...")
                
                # 首先收集所有有效行
                all_valid_rows = []
                for index, row in df.iterrows():
                    # 只处理runOption为Y的行
                    if 'runOption' in df.columns and str(row['runOption']).upper() != 'Y':
                        skipped_rows.append({"row": index+2, "reason": f"runOption不是Y (值为: {str(row['runOption'])})"})
                        continue
                    
                    # 检查oriStep和preScript列
                    ori_step = str(row.get('oriStep', '')).strip()
                    pre_script = str(row.get('preScript', '')).strip()
                    
                    if not ori_step and not pre_script:
                        skipped_rows.append({"row": index+2, "reason": "oriStep和preScript列都为空，用例未识别"})
                        continue
                    
                    # 合并oriStep和preScript中的命令
                    combined_commands = []
                    
                    # 解析oriStep列中的命令
                    if ori_step:
                        ori_commands = ori_step.split(',')
                        for cmd in ori_commands:
                            cmd = cmd.strip()
                            if not cmd:
                                continue
                            combined_commands.append(cmd)
                    # 解析preScript列中的命令
                    if pre_script:
                        pre_commands = pre_script.split(',')
                        for cmd in pre_commands:
                            cmd = cmd.strip()
                            if not cmd:
                                continue
                            combined_commands.append(cmd)
                    
                    # 检查合并后的命令
                    has_valid_command = False
                    for cmd in combined_commands:
                        try:
                            parts = cmd.split('/')
                            if len(parts) == 3:
                                keyname = parts[0].upper()
                                repeat = int(parts[1])
                                delay = float(parts[2])
                                
                                # 验证按键名称
                                if keyname in KEYCODE_MAP:
                                    has_valid_command = True
                        except ValueError:
                            pass
                    
                    if has_valid_command:
                        # 获取用例标题、操作步骤和校验图片
                        title = ''
                        step = ''
                        verify_image = ''
                        test_result = ''
                        
                        # 获取testID
                        if 'testID' in row:
                            test_id_value = row['testID']
                            if test_id_value is not None and str(test_id_value).strip() != '' and str(test_id_value).strip() != 'nan':
                                title = str(test_id_value).strip()
                        
                        # 获取step
                        if 'step' in row:
                            step_value = row['step']
                            if step_value is not None and str(step_value).strip() != '' and str(step_value).strip() != 'nan':
                                step = str(step_value).strip()
                        elif 'operation' in row:
                            operation_value = row['operation']
                            if operation_value is not None and str(operation_value).strip() != '' and str(operation_value).strip() != 'nan':
                                step = str(operation_value).strip()
                        
                        # 获取checkPic
                        if 'checkPic' in row:
                            check_pic_value = row['checkPic']
                            if check_pic_value is not None and str(check_pic_value).strip() != '' and str(check_pic_value).strip() != 'nan':
                                verify_image = str(check_pic_value).strip()
                        
                        # 获取testResult
                        if 'testResult' in row:
                            test_result_value = row['testResult']
                            if test_result_value is not None and str(test_result_value).strip() != '' and str(test_result_value).strip() != 'nan':
                                test_result = str(test_result_value).strip()
                        
                        all_valid_rows.append({"row": index+2, "title": title, "step": step, "verify_image": verify_image, "test_result": test_result, "oriStep": ori_step, "preScript": pre_script, "commands": combined_commands})
                    else:
                        skipped_rows.append({"row": index+2, "reason": "oriStep和preScript列中没有有效命令"})
                
                # 保持原始顺序
                valid_rows = all_valid_rows
                print(f"处理完成：总有效行 {len(valid_rows)} 个")
            else:
                # 原始格式
                required_columns = ['keyname', 'repeat', 'delay']
                for col in required_columns:
                    if col not in df.columns:
                        raise ValueError(f"Excel文件缺少必要的列: {col}")
                
                for index, row in df.iterrows():
                    try:
                        # 检查keyname列
                        keyname = str(row.get('keyname', '')).upper()
                        if not keyname:
                            skipped_rows.append({"row": index+2, "reason": "keyname列为空"})
                            continue
                        
                        # 检查repeat列
                        repeat = int(row.get('repeat', 0))
                        if repeat <= 0:
                            skipped_rows.append({"row": index+2, "reason": "repeat值必须大于0"})
                            continue
                        
                        # 检查delay列
                        delay = float(row.get('delay', 0))
                        if delay < 0:
                            skipped_rows.append({"row": index+2, "reason": "delay值不能小于0"})
                            continue
                        
                        # 验证按键名称
                        if keyname not in KEYCODE_MAP:
                            skipped_rows.append({"row": index+2, "reason": f"keyname '{keyname}' 不存在于按键映射表中"})
                            continue
                        
                        cmd_str = f"{keyname}/{repeat}/{delay}"
                        valid_rows.append({"row": index+2, "command": cmd_str})
                    except (ValueError, TypeError) as e:
                        skipped_rows.append({"row": index+2, "reason": f"数据类型错误: {str(e)}"})
            
            # 如果指定了目标行
            if target_row is not None:
                if 1 <= target_row <= len(valid_rows):
                    valid_row = valid_rows[target_row-1]
                    if "commands" in valid_row:
                        commands = valid_row["commands"]
                    else:
                        commands = [valid_row["command"]]
                    return {
                        "commands": commands,
                        "valid_rows": valid_rows,
                        "skipped_rows": skipped_rows,
                        "executed_row": target_row
                    }
                else:
                    raise ValueError(f"行号 {target_row} 超出范围 (1-{len(valid_rows)})")
            else:
                return {
                    "valid_rows": valid_rows,
                    "skipped_rows": skipped_rows
                }
        except Exception as e:
            print(f"读取Excel文件失败: {e}")
            raise HTTPException(status_code=400, detail=f"读取Excel文件失败: {str(e)}")

# 创建ADB控制器实例
controller = ADBController()

# API路由

@app.get("/api/devices")
async def get_devices():
    """获取设备列表"""
    devices = controller.list_devices()
    return {"devices": devices}

@app.post("/api/devices/select")
async def select_device(request: DeviceSelectRequest):
    """选择设备"""
    device_index = request.device_index
    devices = controller.list_devices()
    if device_index < 1 or device_index > len(devices):
        raise HTTPException(status_code=400, detail=f"无效的设备序号，请输入 1-{len(devices)} 之间的数字")
    
    device_serial = devices[device_index - 1]
    controller.select_device(device_serial)
    global current_device
    current_device = device_serial
    return {"message": f"已选择设备: {device_serial}"}

@app.get("/api/devices/current")
async def get_current_device():
    """获取当前选中的设备"""
    return {"device": current_device}

@app.post("/api/keymonitor/start")
async def api_keymonitor_start():
    if not current_device:
        raise HTTPException(status_code=400, detail="请先选择设备")
    if not monitor_active:
        start_key_monitor_th()
        return {"active": True}
    return {"active": True}

@app.post("/api/keymonitor/stop")
async def api_keymonitor_stop():
    # 在停止前对最后一条做收尾回填：用“最后一次按下(DOWN) -> 停止时刻”的间隔
    try:
        stop_time = time.time()
        global monitor_live_sequence, monitor_dataset_latest, last_key_time
        if monitor_live_sequence:
            lines = monitor_live_sequence.strip().split('\n')
            if lines:
                last_line = lines[-1]
                parts = last_line.split('/')
                if len(parts) >= 3:
                    key = parts[0]
                    count = parts[1]
                    delay_token = parts[2]
                    if delay_token == '*' or delay_token == '0':
                        delay = max(0, math.ceil(stop_time - last_key_time))
                        lines[-1] = f"{key}/{count}/{delay}"
                        monitor_live_sequence = '\n'.join(lines) + '\n'
                        monitor_dataset_latest = monitor_live_sequence
    except Exception:
        pass
    if monitor_active:
        start_key_monitor_th()
    seq = monitor_dataset_latest if monitor_dataset_latest else monitor_live_sequence
    return {"active": False, "sequence": (seq.replace('\n', ',').strip() if seq else "")}

@app.get("/api/keymonitor/status")
async def api_keymonitor_status():
    return {
        "active": monitor_active,
        "stopping": monitor_stopping,
        "live_sequence": monitor_live_sequence.replace('\n', ',').strip(),
        "latest_sequence": monitor_dataset_latest.replace('\n', ',').strip(),
        "last_error": monitor_last_error
    }

@app.post("/api/commands/execute")
async def execute_commands(request: CommandExecuteRequest):
    """执行命令序列"""
@app.post("/api/excel/append_sequence")
async def append_sequence(req: AppendSequenceRequest):
    """将捕获的序列写入到Excel:
       - 若目标文件包含 preScript 列，则在末尾新增一行，runOption=Y, preScript=sequence
       - 否则写入/追加到 captured.xlsx，按原始格式 keyname/repeat/delay 每条一行
    """
    if not req.sequence or not req.sequence.strip():
        raise HTTPException(status_code=400, detail="空序列")
    target = req.file_name.strip()
    if not target:
        raise HTTPException(status_code=400, detail="未指定文件名")
    cwd = os.getcwd()
    target_path = os.path.join(cwd, target)
    try:
        if os.path.exists(target_path):
            df = pd.read_excel(target_path)
            # SmartTV 模板：存在 preScript 列
            if 'preScript' in df.columns:
                new_row = {col: None for col in df.columns}
                if 'runOption' in df.columns:
                    new_row['runOption'] = 'Y'
                new_row['preScript'] = req.sequence
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                try:
                    df.to_excel(target_path, index=False)
                    return {"status": "ok", "file": target, "mode": "smarttv", "rows_added": 1}
                except Exception as e:
                    # 回退到 raw
                    print(f"写入目标文件失败，转raw: {e}")
    except Exception as e:
        # 如果读目标失败，退回到 raw 模式
        print(f"读取目标文件失败，转raw: {e}")
    # raw 模式：写到 captured.xlsx
    raw_file = os.path.join(cwd, "captured.xlsx")
    rows = []
    for item in [x.strip() for x in req.sequence.split(',') if x.strip()]:
        parts = item.split('/')
        if len(parts) >= 3:
            key = parts[0].upper()
            try:
                repeat = int(parts[1])
            except:
                repeat = 1
            try:
                delay = float(parts[2]) if parts[2] != '*' else 0.0
            except:
                delay = 0.0
            rows.append({"keyname": key, "repeat": repeat, "delay": delay})
    cap_df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=['keyname', 'repeat', 'delay'])
    if os.path.exists(raw_file):
        try:
            exist = pd.read_excel(raw_file)
            # 对齐列
            for col in ['keyname', 'repeat', 'delay']:
                if col not in exist.columns:
                    exist[col] = None
            merged = pd.concat([exist[['keyname','repeat','delay']], cap_df], ignore_index=True)
            merged.to_excel(raw_file, index=False)
        except Exception:
            cap_df.to_excel(raw_file, index=False)
    else:
        cap_df.to_excel(raw_file, index=False)
    return {"status": "ok", "file": "captured.xlsx", "mode": "raw", "rows_added": len(rows)}

@app.get("/api/excel/preview")
async def preview_excel(file_name: str, max_rows: int = 50):
    """返回Excel的表头与前N行完整数据，用于页面上显示所有列"""
    if not file_name:
        raise HTTPException(status_code=400, detail="未提供文件名")
    path = os.path.join(os.getcwd(), file_name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="文件不存在")
    try:
        df = pd.read_excel(path)
        cols = list(df.columns)
        rows = df.head(max(1, min(max_rows, 200))).fillna('').astype(str).to_dict(orient='records')
        return {"columns": cols, "rows": rows, "row_count": len(df)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取Excel失败: {e}")

@app.post("/api/excel/write_cell")
async def write_cell(req: WriteCellRequest):
    if not req.file_name or not req.column_name:
        raise HTTPException(status_code=400, detail="缺少参数")
    path = os.path.join(os.getcwd(), req.file_name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="文件不存在")
    try:
        df = pd.read_excel(path)
        col = req.column_name
        if col not in df.columns:
            df[col] = None
        ri = int(req.row_index)
        if ri < 0:
            ri = 0
        if ri >= len(df):
            df = df.reindex(range(ri + 1))
        df.loc[ri, col] = req.value
        df.to_excel(path, index=False)
        return {"status": "ok", "file": req.file_name, "row_index": ri, "column_name": col}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入失败: {e}")

@app.post("/api/commands/execute")
async def execute_commands(request: CommandExecuteRequest):
    """执行命令序列"""
    if not current_device:
        raise HTTPException(status_code=400, detail="请先选择设备")
    
    results = controller.execute_commands(request.commands)
    return {"results": results}

@app.get("/api/excel/files")
async def get_excel_files():
    """获取当前工作目录下的Excel文件"""
    excel_files = []
    current_dir = os.getcwd()
    if os.path.exists(current_dir) and os.path.isdir(current_dir):
        for file in os.listdir(current_dir):
            if file.endswith('.xlsx') or file.endswith('.xls'):
                excel_files.append(file)
    
    return {"files": excel_files}

from fastapi import UploadFile, File

@app.get("/api/excel/analyze")
async def analyze_excel_file(file_name: str):
    """分析Excel文件内容"""
    # 构建当前目录下的文件路径
    file_path = os.path.join(os.getcwd(), file_name)
    print(f"开始分析文件: {file_path}")
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        raise HTTPException(status_code=404, detail="文件不存在")
    
    try:
        print(f"调用read_excel_commands")
        result = controller.read_excel_commands(file_path)
        print(f"分析完成，有效行数: {len(result.get('valid_rows', []))}")
        return result
    except Exception as e:
        print(f"分析文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析文件失败: {str(e)}")

@app.post("/api/excel/upload")
async def upload_excel_file(file: UploadFile = File(...)):
    """上传Excel文件"""
    # 检查文件扩展名
    if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        raise HTTPException(status_code=400, detail="只支持 .xlsx 和 .xls 格式的文件")
    
    # 保存文件到当前目录
    file_path = os.path.join(os.getcwd(), file.filename)
    
    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        return {"filename": file.filename, "message": "文件上传成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传文件失败: {str(e)}")

@app.post("/api/execute")
async def execute_command(request: SingleCommandExecuteRequest):
    """执行单个命令"""
    if not current_device:
        raise HTTPException(status_code=400, detail="请先选择设备")
    
    command = request.command
    if not command:
        raise HTTPException(status_code=400, detail="请提供命令")
    
    # 执行命令
    execution_results = controller.execute_commands(command)
    
    return {
        "execution_results": execution_results,
        "executed_command": command
    }

from fastapi.responses import StreamingResponse
from fastapi import Request
import asyncio

@app.post("/api/excel/execute")
async def execute_excel_commands(request: Request):
    """执行Excel文件中的命令"""
    if not current_device:
        raise HTTPException(status_code=400, detail="请先选择设备")
    
    # 直接读取请求体
    body = await request.json()
    file_name = body.get('file_name')
    row_index = body.get('row_index')
    
    if not file_name or not row_index:
        raise HTTPException(status_code=400, detail="请提供文件名和行号")
    
    # 转换row_index为整数
    try:
        row_index = int(row_index)
    except ValueError:
        raise HTTPException(status_code=400, detail="行号必须是整数")
    
    # 构建当前目录下的文件路径
    file_path = os.path.join(os.getcwd(), file_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    result = controller.read_excel_commands(file_path, row_index)
    commands = result["commands"]
    
    # 获取用例标题
    test_title = None
    if "valid_rows" in result:
        valid_rows = result["valid_rows"]
        if 1 <= row_index <= len(valid_rows):
            executed_row = valid_rows[row_index - 1]
            if "title" in executed_row and executed_row["title"]:
                test_title = executed_row["title"]
    
    async def event_generator():
        # 执行命令
        for cmd in commands:
            # 跳过nan命令
            if cmd.strip().lower() == 'nan':
                continue
            # 解析命令
            parts = cmd.strip().split('/')
            if len(parts) != 3:
                import json
                yield f"data: {json.dumps({'status': 'error', 'message': f'命令格式错误: {cmd}'})}\n\n"
                continue
            
            keyname, repeat, delay = parts
            keyname = keyname.upper()
            
            if keyname not in KEYCODE_MAP:
                import json
                yield f"data: {json.dumps({'status': 'error', 'message': f'未知按键: {keyname}'})}\n\n"
                continue
            
            try:
                repeat = int(repeat)
                delay = float(delay)
            except ValueError:
                import json
                yield f"data: {json.dumps({'status': 'error', 'message': f'命令参数错误: {cmd}'})}\n\n"
                continue
            
            keycode = KEYCODE_MAP[keyname]
            
            # 逐个执行按键
            for _ in range(repeat):
                import json
                # 发送"正在发送"的日志
                yield f"data: {json.dumps({'status': 'info', 'message': f'正在发送: {keyname}'})}\n\n"
                await asyncio.sleep(0.01)  # 短暂延迟确保日志发送
                
                # 执行命令
                controller.send_keyevent(keycode, keyname, delay)
                
                # 等待一段时间，模拟实时效果
                await asyncio.sleep(0.1)
        
        # 所有命令执行完成后截图
        import json
        yield f"data: {json.dumps({'status': 'info', 'message': '正在截图...'})}\n\n"
        await asyncio.sleep(0.4)
        
        screenshot_path = controller.take_screenshot(test_title)
        if screenshot_path:
            # 生成截图的访问路径
            screenshot_url = f"/api/screenshot/{os.path.basename(screenshot_path)}"
            yield f"data: {json.dumps({'status': 'success', 'message': '截图成功', 'screenshot_url': screenshot_url})}\n\n"
        else:
            yield f"data: {json.dumps({'status': 'error', 'message': '截图失败'})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.delete("/api/excel/delete")
async def delete_excel_file(file_name: str):
    """删除Excel文件"""
    if not file_name:
        raise HTTPException(status_code=400, detail="请提供文件名")
    
    # 构建当前目录下的文件路径
    file_path = os.path.join(os.getcwd(), file_name)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    try:
        os.remove(file_path)
        return {"message": f"文件 {file_name} 已成功删除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")

@app.get("/api/screenshot")
async def get_screenshots():
    """获取所有截图的列表"""
    import glob
    screenshots = glob.glob("screenshot_*.png")
    screenshots.sort(key=os.path.getmtime, reverse=True)
    
    screenshot_list = []
    for screenshot in screenshots:
        screenshot_name = os.path.basename(screenshot)
        screenshot_list.append({
            "name": screenshot_name,
            "url": f"/api/screenshot/{screenshot_name}",
            "timestamp": os.path.getmtime(screenshot)
        })
    
    return {"screenshots": screenshot_list}

@app.get("/api/screenshot/{screenshot_name}")
async def get_screenshot(screenshot_name: str):
    """获取特定的截图"""
    screenshot_path = os.path.join(os.getcwd(), screenshot_name)
    
    if not os.path.exists(screenshot_path):
        raise HTTPException(status_code=404, detail="截图不存在")
    
    return FileResponse(screenshot_path, media_type="image/png")

@app.delete("/api/screenshot/clear")
async def clear_screenshots():
    """清除所有截图"""
    try:
        import glob
        # 匹配所有.png文件
        screenshots = glob.glob("*.png")
        deleted_count = 0
        for screenshot in screenshots:
            try:
                os.remove(screenshot)
                deleted_count += 1
            except Exception as e:
                print(f"删除截图 {screenshot} 失败: {e}")
        return {"status": "ok", "deleted_count": deleted_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除截图失败: {str(e)}")

# 前端静态资源服务（用于打包单EXE运行）
try:
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.extend([
            os.path.join(meipass, "frontend", "dist"),
            os.path.join(meipass, "dist"),
        ])
    project_root = os.path.dirname(os.path.dirname(__file__))
    candidates.extend([
        os.path.join(project_root, "frontend", "dist"),
        os.path.join(os.getcwd(), "frontend", "dist"),
        os.path.join(os.getcwd(), "dist"),
    ])
    FRONTEND_DIST = next((p for p in candidates if os.path.isdir(p)), None)
    if FRONTEND_DIST:
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="static")
except Exception:
    pass

# 启动应用
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
