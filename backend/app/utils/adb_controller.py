"""ADB控制器工具模块"""
import subprocess
import time
import os
import re
import json
import pandas as pd
from typing import List, Optional, Dict, Any
from ..config import settings

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
    "SRTTING": 176,
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
    "PRIME_VIDEO": 134,
    "PRIME_VII": 134,
    "ACTION3": 222,
    "ACTIONS": 222,
    "FILES": 359,
    "RED": 1,
    "GREEN": 2,
    "YELLOW": 3,
    "BLUE": 4,
    "INFORMATION": 7,
    "MUTE": 164
}


def get_keycode_map() -> dict:
    """返回合并后的键值映射：KEYCODE_MAP 默认值 + 当前激活方案的 key_codes 覆盖。"""
    merged = dict(KEYCODE_MAP)
    try:
        path = settings.CUSTOMIZATION_FILE
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 同时兼容旧扁平格式和新方案格式
            if "schemes" in data:
                active = data.get("active_scheme", "默认")
                scheme = data.get("schemes", {}).get(active, {})
                custom = scheme.get("key_codes", {})
            else:
                custom = data.get("key_codes", {})
            if isinstance(custom, dict):
                for k, v in custom.items():
                    if isinstance(k, str) and k.strip() and isinstance(v, int):
                        merged[k.strip().upper()] = v
    except Exception:
        pass
    return merged


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

    def _normalize_excel_text(self, value: Any) -> str:
        if value is None or pd.isna(value):
            return ""
        return str(value).strip()

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
        keycode_map = get_keycode_map()
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

                if keyname not in keycode_map:
                    results.append({"status": "error", "message": f"未知按键: {keyname}"})
                    continue

                keycode = keycode_map[keyname]
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

    def _adb_command(self, *args: str) -> List[str]:
        command = ["adb"]
        if self.device_serial:
            command.extend(["-s", self.device_serial])
        command.extend(args)
        return command

    def get_last_tts_text(self, tail_count: int = 200) -> Optional[str]:
        """从最近的 logcat 输出中提取最后一条 tts aric char 文本。"""
        try:
            result = subprocess.run(
                self._adb_command("logcat", "-d", "-t", str(max(1, int(tail_count)))),
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
        except (subprocess.CalledProcessError, OSError, ValueError) as e:
            print(f"读取 TTS logcat 失败: {e}")
            return None

        matches = re.findall(r'tts aric char\s*=\s*"([^"]*)"', result.stdout, flags=re.IGNORECASE)
        if matches:
            return matches[-1].strip()

        lines = [line.strip() for line in result.stdout.splitlines() if "tts aric char" in line.lower()]
        if not lines:
            return None

        last_line = lines[-1]
        if "=" in last_line:
            return last_line.split("=", 1)[1].strip().strip('"')
        return last_line

    def _remove_local_file(self, file_path) -> None:
        try:
            if file_path.exists():
                file_path.unlink()
        except OSError:
            pass

    def _cleanup_remote_file(self, remote_path: str) -> None:
        try:
            subprocess.run(
                self._adb_command("shell", "rm", remote_path),
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            pass

    def _is_valid_png(self, file_path) -> bool:
        try:
            if not file_path.exists() or file_path.stat().st_size <= 8:
                return False
            with file_path.open("rb") as image_file:
                return image_file.read(8) == b"\x89PNG\r\n\x1a\n"
        except OSError:
            return False

    def _take_screenshot_via_exec_out(self, local_path) -> bool:
        try:
            with local_path.open("wb") as image_file:
                subprocess.run(
                    self._adb_command("exec-out", "screencap", "-p"),
                    check=True,
                    stdout=image_file,
                    stderr=subprocess.PIPE,
                )
        except (subprocess.CalledProcessError, OSError) as e:
            self._remove_local_file(local_path)
            print(f"exec-out截图失败: {e}")
            return False

        if self._is_valid_png(local_path):
            print(f"截图成功，保存到: {local_path}")
            return True

        self._remove_local_file(local_path)
        print("exec-out截图失败: 输出不是有效PNG")
        return False

    def _take_screenshot_via_remote_file(self, local_path, file_name: str) -> Optional[str]:
        remote_candidates = [
            f"/data/local/tmp/{file_name}",
            f"/sdcard/{file_name}",
        ]

        for remote_path in remote_candidates:
            try:
                subprocess.run(
                    self._adb_command("shell", "screencap", "-p", remote_path),
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )

                for attempt in range(3):
                    try:
                        subprocess.run(
                            self._adb_command("pull", remote_path, str(local_path)),
                            check=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                        )
                    except subprocess.CalledProcessError as e:
                        self._remove_local_file(local_path)
                        print(f"截图拉取失败（尝试 {attempt + 1}/3，{remote_path}）: {e}")
                        time.sleep(0.3)
                        continue

                    if self._is_valid_png(local_path):
                        print(f"截图成功，保存到: {local_path}")
                        return str(local_path)

                    self._remove_local_file(local_path)
                    print(f"截图文件无效（尝试 {attempt + 1}/3，{remote_path}）")
                    time.sleep(0.3)
            except subprocess.CalledProcessError as e:
                self._remove_local_file(local_path)
                print(f"截图失败（尝试 {remote_path}）: {e}")
                time.sleep(0.2)
            finally:
                self._cleanup_remote_file(remote_path)

        return None

    def take_screenshot(self, title: Optional[str] = None) -> Optional[str]:
        """使用ADB截图"""
        if title:
            safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)
            file_name = f"{safe_title}.png"
        else:
            ts = int(time.time() * 1000)
            file_name = f"screenshot_{ts}.png"

        local_path = settings.SCREENSHOT_DIR / file_name

        if self._take_screenshot_via_exec_out(local_path):
            return str(local_path)

        return self._take_screenshot_via_remote_file(local_path, file_name)

    def read_excel_commands(self, excel_path: str, target_row: Optional[int] = None) -> Dict[str, Any]:
        """读取Excel文件中的命令"""
        keycode_map = get_keycode_map()
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

                    ori_step = self._normalize_excel_text(row.get('oriStep', ''))
                    pre_script = self._normalize_excel_text(row.get('preScript', ''))

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

                                if keyname in keycode_map:
                                    has_valid_command = True
                        except ValueError:
                            pass

                    if has_valid_command:
                        title = ''
                        step = ''
                        verify_image = ''
                        test_result = ''

                        if 'testID' in row:
                            title = self._normalize_excel_text(row['testID'])

                        if 'step' in row:
                            step = self._normalize_excel_text(row['step'])
                        elif 'operation' in row:
                            step = self._normalize_excel_text(row['operation'])

                        if 'checkPic' in row:
                            verify_image = self._normalize_excel_text(row['checkPic'])

                        if 'testResult' in row:
                            test_result = self._normalize_excel_text(row['testResult'])

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

                        if keyname not in keycode_map:
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
