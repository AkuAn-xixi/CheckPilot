"""ADB控制器工具模块"""
import subprocess
import time
import os
import re
import pandas as pd
from typing import List, Optional, Dict, Any

KEYCODE_MAP = {
    "OK": 23,
    "HOME": 3,
    "BACK": 4,
    "UP": 19,
    "DOWN": 20,
    "LEFT": 21,
    "RIGHT": 22,
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

class ADBController:
    """ADB设备控制器"""

    def __init__(self):
        self.device_serial: Optional[str] = None

    def list_devices(self) -> List[str]:
        """列出所有连接的ADB设备"""
        try:
            result = subprocess.run(
                "adb devices",
                shell=True,
                check=True,
                capture_output=True,
                text=True
            )
            lines = result.stdout.splitlines()
            devices = []

            for line in lines[1:]:
                if line.strip() and "device" in line:
                    serial = line.split('\t')[0]
                    devices.append(serial)

            return devices
        except subprocess.CalledProcessError as e:
            print(f"获取设备列表失败: {e}")
            return []

    def select_device(self, device_serial: str) -> bool:
        """选择要连接的ADB设备"""
        self.device_serial = device_serial
        return True

    def send_keyevent(self, keycode: int, keyname: str, delay: float = 0) -> bool:
        """发送ADB keyevent并可选延迟"""
        if not 1 <= keycode <= 999:
            raise ValueError("Keycode must be between 1 and 999")

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

    def execute_commands(self, command_sequence: str) -> List[Dict[str, Any]]:
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

    def take_screenshot(self, title: Optional[str] = None) -> Optional[str]:
        """使用ADB截图"""
        device_arg = f"-s {self.device_serial} " if self.device_serial else ""

        if title:
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

                try:
                    subprocess.run(f"adb {device_arg}shell rm {remote_path}", shell=True)
                except Exception:
                    pass

                print(f"截图成功，保存到: {local_path}")
                return local_path
            except subprocess.CalledProcessError as e:
                print(f"截图失败（尝试 {remote_path}）: {e}")
                time.sleep(0.2)
                continue

        return None

    def read_excel_commands(self, excel_path: str, target_row: Optional[int] = None) -> Dict[str, Any]:
        """读取Excel文件中的命令"""
        try:
            df = pd.read_excel(excel_path)

            commands = []
            valid_rows = []
            skipped_rows = []

            if 'preScript' in df.columns:
                print("检测到SmartTV模板格式，正在解析preScript列...")

                all_valid_rows = []
                for index, row in df.iterrows():
                    if 'runOption' in df.columns and str(row['runOption']).upper() != 'Y':
                        skipped_rows.append({"row": index+2, "reason": f"runOption不是Y (值为: {str(row['runOption'])})"})
                        continue

                    ori_step = str(row.get('oriStep', '')).strip()
                    pre_script = str(row.get('preScript', '')).strip()

                    if not ori_step and not pre_script:
                        skipped_rows.append({"row": index+2, "reason": "oriStep和preScript列都为空，用例未识别"})
                        continue

                    combined_commands = []

                    if ori_step:
                        ori_commands = ori_step.split(',')
                        for cmd in ori_commands:
                            cmd = cmd.strip()
                            if not cmd:
                                continue
                            combined_commands.append(cmd)

                    if pre_script:
                        pre_commands = pre_script.split(',')
                        for cmd in pre_commands:
                            cmd = cmd.strip()
                            if not cmd:
                                continue
                            combined_commands.append(cmd)

                    has_valid_command = False
                    for cmd in combined_commands:
                        try:
                            parts = cmd.split('/')
                            if len(parts) == 3:
                                keyname = parts[0].upper()
                                repeat = int(parts[1])
                                delay = float(parts[2])

                                if keyname in KEYCODE_MAP:
                                    has_valid_command = True
                        except ValueError:
                            pass

                    if has_valid_command:
                        title = ''
                        step = ''
                        verify_image = ''
                        test_result = ''

                        if 'testID' in row:
                            test_id_value = row['testID']
                            if test_id_value is not None and str(test_id_value).strip() != '' and str(test_id_value).strip() != 'nan':
                                title = str(test_id_value).strip()

                        if 'step' in row:
                            step_value = row['step']
                            if step_value is not None and str(step_value).strip() != '' and str(step_value).strip() != 'nan':
                                step = str(step_value).strip()
                        elif 'operation' in row:
                            operation_value = row['operation']
                            if operation_value is not None and str(operation_value).strip() != '' and str(operation_value).strip() != 'nan':
                                step = str(operation_value).strip()

                        if 'checkPic' in row:
                            check_pic_value = row['checkPic']
                            if check_pic_value is not None and str(check_pic_value).strip() != '' and str(check_pic_value).strip() != 'nan':
                                verify_image = str(check_pic_value).strip()

                        if 'testResult' in row:
                            test_result_value = row['testResult']
                            if test_result_value is not None and str(test_result_value).strip() != '' and str(test_result_value).strip() != 'nan':
                                test_result = str(test_result_value).strip()

                        all_valid_rows.append({
                            "row": index+2,
                            "title": title,
                            "step": step,
                            "verify_image": verify_image,
                            "test_result": test_result,
                            "oriStep": ori_step,
                            "preScript": pre_script,
                            "commands": combined_commands
                        })
                    else:
                        skipped_rows.append({"row": index+2, "reason": "oriStep和preScript列中没有有效命令"})

                valid_rows = all_valid_rows
                print(f"处理完成：总有效行 {len(valid_rows)} 个")
            else:
                required_columns = ['keyname', 'repeat', 'delay']
                for col in required_columns:
                    if col not in df.columns:
                        raise ValueError(f"Excel文件缺少必要的列: {col}")

                for index, row in df.iterrows():
                    try:
                        keyname = str(row.get('keyname', '')).upper()
                        if not keyname:
                            skipped_rows.append({"row": index+2, "reason": "keyname列为空"})
                            continue

                        repeat = int(row.get('repeat', 0))
                        if repeat <= 0:
                            skipped_rows.append({"row": index+2, "reason": "repeat值必须大于0"})
                            continue

                        delay = float(row.get('delay', 0))
                        if delay < 0:
                            skipped_rows.append({"row": index+2, "reason": "delay值不能小于0"})
                            continue

                        if keyname not in KEYCODE_MAP:
                            skipped_rows.append({"row": index+2, "reason": f"keyname '{keyname}' 不存在于按键映射表中"})
                            continue

                        cmd_str = f"{keyname}/{repeat}/{delay}"
                        valid_rows.append({"row": index+2, "command": cmd_str})
                    except (ValueError, TypeError) as e:
                        skipped_rows.append({"row": index+2, "reason": f"数据类型错误: {str(e)}"})

            commands = valid_rows[target_row - 1]["commands"] if target_row and target_row <= len(valid_rows) else []

            return {
                "commands": commands,
                "valid_rows": valid_rows,
                "skipped_rows": skipped_rows,
                "total_rows": len(valid_rows)
            }
        except Exception as e:
            raise Exception(f"读取Excel失败: {e}")
