"""ADB控制器工具模块"""
import subprocess
import time
import os
import re
import json
import logging
import threading
from datetime import datetime
import pandas as pd
from typing import List, Optional, Dict, Any
from ..config import settings
from ...FieldValidation import get_valid_keys as get_runtime_valid_keys

logger = logging.getLogger(__name__)

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
    "DISCOVERY": 358,
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
    "MUTE": 164,
    # ASSERT 是步骤分隔/断言占位符，不发实际 keyevent，但要被校验/解析当成有效按键。
    # 实际执行时会被 NON_EXECUTABLE_KEYS 拦截跳过，keycode 0 仅作占位。
    "ASSERT": 0,
}

# 这些"有效按键"在解析层是合法的，但执行时不发 adb keyevent。
NON_EXECUTABLE_KEYS = frozenset({"ASSERT"})


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


def format_timestamped_log(message: str) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"[{timestamp}] {message}"


def console_log(message: str) -> None:
    print(format_timestamped_log(message), flush=True)


def apply_min_command_delay(delay: float) -> float:
    """把命令延迟规整为最终生效的等待时间。

    最终等待 = max(用户给的 delay, ``settings.COMMAND_MIN_DELAY_SECONDS``)
              + ``customization.json::extra_command_delay``

    - ``COMMAND_MIN_DELAY_SECONDS``：兜底硬阈值，默认 0，可在 settings 里启用。
    - ``extra_command_delay``：用户在客制化页面配置的全局额外等待秒数。

    示例：用户写 ``HOME/1/0.5``，extra=1 → 实际等待 1.5 秒；
    用户写 ``HOME/1/2``，extra=1 → 实际等待 3 秒。
    """
    try:
        delay_value = float(delay)
    except (TypeError, ValueError):
        delay_value = 0.0
    if delay_value < 0:
        delay_value = 0.0

    minimum = float(getattr(settings, "COMMAND_MIN_DELAY_SECONDS", 0) or 0)
    if minimum > 0 and delay_value < minimum:
        delay_value = minimum

    extra = _get_extra_command_delay()
    if extra > 0:
        delay_value += extra

    return delay_value


def _get_extra_command_delay() -> float:
    """读取客制化配置里的额外等待秒数。延迟导入，避免循环依赖。"""
    try:
        from ..api.customization import get_extra_command_delay
    except Exception:
        return 0.0
    try:
        return max(0.0, float(get_extra_command_delay() or 0))
    except Exception:
        return 0.0


class ADBController:
    """ADB设备控制器"""

    def __init__(self):
        self.device_serial: Optional[str] = None
        self._stop_event = threading.Event()
        self._execution_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._is_executing = False
        self._recording_process: Optional[subprocess.Popen] = None
        self._recording_remote_path: Optional[str] = None
        # Excel 解析缓存：(文件路径, mtime) -> 解析结果
        self._excel_cache_path: Optional[str] = None
        self._excel_cache_mtime: float = 0.0
        self._excel_cache_result: Optional[Dict[str, Any]] = None

    def _set_executing(self, value: bool) -> None:
        with self._state_lock:
            self._is_executing = value

    def is_executing(self) -> bool:
        with self._state_lock:
            return self._is_executing

    def request_stop(self) -> bool:
        if not self.is_executing():
            return False

        self._stop_event.set()
        return True

    def _should_stop_execution(self) -> bool:
        return self._stop_event.is_set()

    def _wait_with_stop(self, delay: float) -> bool:
        if delay <= 0:
            return True

        deadline = time.perf_counter() + delay
        while True:
            if self._should_stop_execution():
                return False

            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                return True

            time.sleep(min(0.1, remaining))

    @staticmethod
    def _append_stopped_result(results: List[Dict[str, Any]]) -> None:
        if results and results[-1].get("message") == "命令执行已停止":
            return

        results.append({"status": "info", "message": "命令执行已停止"})

    def list_devices(self, timeout: float = 5.0) -> List[str]:
        """列出所有连接的ADB设备。

        通过 ``timeout`` 限定 ``adb devices`` 的最大等待时间，避免 ADB server
        卡住时阻塞调用方（例如 FastAPI 接口）。失败或超时时返回空列表，让上层
        能与"真的没设备"区分（调用方可结合自身状态决定是否保留旧设备）。
        """
        logger.info("[ADB] 扫描设备列表 (timeout=%.1fs)", timeout)
        t0 = time.perf_counter()
        try:
            result = subprocess.run(
                "adb devices",
                shell=True,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.error("[ADB] ✗ 扫描设备超时 (耗时=%.0fms, timeout=%.1fs)，可能需要重启 adb server", elapsed_ms, timeout)
            console_log(f"获取设备列表超时（>{timeout}s），可能需要重启 adb server")
            return []
        except subprocess.CalledProcessError as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.error("[ADB] ✗ 扫描设备失败 (耗时=%.0fms): %s", elapsed_ms, e)
            console_log(f"获取设备列表失败: {e}")
            return []

        elapsed_ms = (time.perf_counter() - t0) * 1000
        lines = result.stdout.splitlines()
        devices = []
        for line in lines[1:]:
            if line.strip() and "device" in line:
                serial = line.split('\t')[0]
                devices.append(serial)
        logger.info("[ADB] ✓ 扫描完成 (耗时=%.0fms): 发现 %d 个设备 %s", elapsed_ms, len(devices), devices)
        return devices

    def select_device(self, device_serial: str) -> bool:
        """选择要连接的ADB设备"""
        old_serial = self.device_serial
        self.device_serial = device_serial
        logger.info("[ADB] 设备切换: %s -> %s", old_serial or '无', device_serial)
        return True

    def _normalize_excel_text(self, value: Any) -> str:
        if value is None or pd.isna(value):
            return ""
        return str(value).strip()

    def send_keyevent(self, keycode: int, keyname: str, delay: float = 0) -> bool:
        """发送ADB keyevent并可选延迟"""
        if not 1 <= keycode <= 999:
            raise ValueError("Keycode must be between 1 and 999")

        cmd = self._adb_command("shell", "input", "keyevent", str(keycode))
        device_info = self.device_serial or "auto"

        logger.info("[ADB] ▶ 发送按键: keyname=%s, keycode=%d, device=%s, delay=%.2fs",
                    keyname, keycode, device_info, delay)
        t0 = time.perf_counter()

        try:
            result = subprocess.run(cmd, check=True,
                                    capture_output=True, text=True, timeout=10)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.info("[ADB] ✓ 按键成功: keyname=%s, keycode=%d, 耗时=%.0fms, device=%s",
                        keyname, keycode, elapsed_ms, device_info)
            if result.stdout.strip():
                logger.debug("[ADB]   stdout: %s", result.stdout.strip())
            if delay > 0:
                logger.info("[ADB]   等待 %.2fs ...", delay)
                if not self._wait_with_stop(delay):
                    logger.info("[ADB]   收到停止请求，结束 %s 的等待阶段", keyname)
            return True
        except subprocess.CalledProcessError as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.error("[ADB] ✗ 按键失败: keyname=%s, keycode=%d, 耗时=%.0fms, device=%s, returncode=%d, stderr=%s",
                         keyname, keycode, elapsed_ms, device_info, e.returncode, (e.stderr or '').strip())
            console_log(f"发送 {keyname} ({keycode}) 失败: {e}")
            return False
        except subprocess.TimeoutExpired:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.error("[ADB] ✗ 按键超时: keyname=%s, keycode=%d, 耗时=%.0fms, device=%s",
                         keyname, keycode, elapsed_ms, device_info)
            return False

    def execute_commands(self, command_sequence: str) -> List[Dict[str, Any]]:
        """执行多条ADB命令"""
        keycode_map = get_keycode_map()
        commands = command_sequence.split(',')
        results = []
        logger.info("[ADB] ═══ 批量执行开始: 共 %d 条命令, device=%s ═══",
                    len(commands), self.device_serial or "auto")

        with self._execution_lock:
            self._stop_event.clear()
            self._set_executing(True)

            try:
                for cmd in commands:
                    if self._should_stop_execution():
                        self._append_stopped_result(results)
                        break

                    try:
                        parts = cmd.strip().split('/')
                        if len(parts) != 3:
                            results.append({"status": "error", "message": f"命令格式错误: {cmd}"})
                            continue

                        keyname, repeat, delay = parts
                        keyname = keyname.upper()
                        repeat = int(repeat)
                        delay = apply_min_command_delay(float(delay))

                        if keyname not in keycode_map:
                            results.append({"status": "error", "message": f"未知按键: {keyname}"})
                            continue

                        if keyname in NON_EXECUTABLE_KEYS:
                            # ASSERT 等占位按键不发实际 keyevent，但保留指令的延迟语义
                            results.append({"status": "success", "message": f"已跳过非执行按键: {keyname}"})
                            for _ in range(repeat):
                                if self._should_stop_execution():
                                    self._append_stopped_result(results)
                                    return results
                                if not self._wait_with_stop(delay):
                                    self._append_stopped_result(results)
                                    return results
                            continue

                        keycode = keycode_map[keyname]
                        for _ in range(repeat):
                            if self._should_stop_execution():
                                self._append_stopped_result(results)
                                return results

                            success = self.send_keyevent(keycode, keyname, delay)
                            if success:
                                results.append({"status": "success", "message": f"已发送: {keyname}"})
                                if self._should_stop_execution():
                                    self._append_stopped_result(results)
                                    return results
                            else:
                                results.append({"status": "error", "message": f"发送失败: {keyname}"})
                                break
                    except ValueError as e:
                        results.append({"status": "error", "message": f"命令执行错误: {e}"})

                success_count = sum(1 for r in results if r.get("status") == "success")
                error_count = sum(1 for r in results if r.get("status") == "error")
                logger.info("[ADB] ═══ 批量执行完成: 成功=%d, 失败=%d, 总计=%d ═══",
                            success_count, error_count, len(results))
                return results
            finally:
                self._set_executing(False)
                self._stop_event.clear()

    def _adb_command(self, *args: str) -> List[str]:
        command = ["adb"]
        if self.device_serial:
            command.extend(["-s", self.device_serial])
        command.extend(args)
        return command

    def clear_logcat(self) -> None:
        """清空设备 logcat 缓冲区。"""
        try:
            subprocess.run(
                self._adb_command("logcat", "-c"),
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            pass

    def get_last_tts_text(self, tail_count: int = 200) -> Optional[str]:
        """从最近的 logcat 输出中提取最后一条 handleTtsContent 文本。"""
        try:
            # 不限制行数，因为每次执行前已清空 logcat，缓冲区只有本次命令的日志
            result = subprocess.run(
                self._adb_command("logcat", "-d"),
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
        except (subprocess.CalledProcessError, OSError, ValueError) as e:
            console_log(f"读取 TTS logcat 失败: {e}")
            return None

        logcat_lines = result.stdout.splitlines()

        # 从 "handleTtsContent: content:xxx#" 行提取 TTS 文本
        for line in reversed(logcat_lines):
            marker = "handleTtsContent: content:"
            idx = line.find(marker)
            if idx == -1:
                continue
            start = idx + len(marker)
            end = line.find("#", start)
            value = line[start:end].strip() if end != -1 else line[start:].strip()
            if value:
                console_log(f"TTS 输出文本: {value}")
                return value

        console_log("未捕获到 TTS 输出文本")
        return None

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
        device_info = self.device_serial or "auto"
        logger.info("[ADB] 📷 尝试 exec-out 截图: device=%s, target=%s", device_info, local_path.name)
        t0 = time.perf_counter()
        try:
            with local_path.open("wb") as image_file:
                subprocess.run(
                    self._adb_command("exec-out", "screencap", "-p"),
                    check=True,
                    stdout=image_file,
                    stderr=subprocess.PIPE,
                    timeout=15,
                )
        except subprocess.TimeoutExpired:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            self._remove_local_file(local_path)
            logger.error("[ADB] ✗ exec-out 截图超时: device=%s, 耗时=%.0fms", device_info, elapsed_ms)
            return False
        except (subprocess.CalledProcessError, OSError) as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            self._remove_local_file(local_path)
            logger.error("[ADB] ✗ exec-out 截图失败: device=%s, 耗时=%.0fms, error=%s", device_info, elapsed_ms, e)
            console_log(f"exec-out截图失败: {e}")
            return False

        elapsed_ms = (time.perf_counter() - t0) * 1000
        if self._is_valid_png(local_path):
            file_size = local_path.stat().st_size
            logger.info("[ADB] ✓ exec-out 截图成功: %s (%.1fKB, 耗时=%.0fms)", local_path.name, file_size / 1024, elapsed_ms)
            console_log(f"截图成功，保存到: {local_path}")
            return True

        self._remove_local_file(local_path)
        logger.warning("[ADB] ✗ exec-out 截图失败: 输出不是有效PNG, 耗时=%.0fms", elapsed_ms)
        console_log("exec-out截图失败: 输出不是有效PNG")
        return False

    def _take_screenshot_via_remote_file(self, local_path, file_name: str) -> Optional[str]:
        device_info = self.device_serial or "auto"
        remote_candidates = [
            f"/data/local/tmp/{file_name}",
            f"/sdcard/{file_name}",
        ]
        logger.info("[ADB] 📷 尝试 remote-file 截图: device=%s, file=%s", device_info, file_name)
        t_total = time.perf_counter()

        for remote_path in remote_candidates:
            try:
                t_screencap = time.perf_counter()
                subprocess.run(
                    self._adb_command("shell", "screencap", "-p", remote_path),
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    timeout=15,
                )
                screencap_ms = (time.perf_counter() - t_screencap) * 1000
                logger.info("[ADB]   screencap 完成: remote=%s, 耗时=%.0fms", remote_path, screencap_ms)

                for attempt in range(3):
                    t_pull = time.perf_counter()
                    try:
                        subprocess.run(
                            self._adb_command("pull", remote_path, str(local_path)),
                            check=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            timeout=15,
                        )
                    except subprocess.CalledProcessError as e:
                        pull_ms = (time.perf_counter() - t_pull) * 1000
                        self._remove_local_file(local_path)
                        logger.warning("[ADB]   pull 失败 (尝试 %d/3): remote=%s, 耗时=%.0fms, error=%s",
                                       attempt + 1, remote_path, pull_ms, e)
                        console_log(f"截图拉取失败（尝试 {attempt + 1}/3，{remote_path}）: {e}")
                        time.sleep(0.3)
                        continue
                    except subprocess.TimeoutExpired:
                        pull_ms = (time.perf_counter() - t_pull) * 1000
                        self._remove_local_file(local_path)
                        logger.warning("[ADB]   pull 超时 (尝试 %d/3): remote=%s, 耗时=%.0fms",
                                       attempt + 1, remote_path, pull_ms)
                        time.sleep(0.3)
                        continue

                    pull_ms = (time.perf_counter() - t_pull) * 1000
                    if self._is_valid_png(local_path):
                        file_size = local_path.stat().st_size
                        total_ms = (time.perf_counter() - t_total) * 1000
                        logger.info("[ADB] ✓ remote-file 截图成功: %s (%.1fKB, pull=%.0fms, 总耗时=%.0fms)",
                                    local_path.name, file_size / 1024, pull_ms, total_ms)
                        console_log(f"截图成功，保存到: {local_path}")
                        return str(local_path)

                    self._remove_local_file(local_path)
                    logger.warning("[ADB]   pull 文件无效 (尝试 %d/3): remote=%s", attempt + 1, remote_path)
                    console_log(f"截图文件无效（尝试 {attempt + 1}/3，{remote_path}）")
                    time.sleep(0.3)
            except subprocess.CalledProcessError as e:
                self._remove_local_file(local_path)
                logger.error("[ADB]   screencap 失败: remote=%s, error=%s", remote_path, e)
                console_log(f"截图失败（尝试 {remote_path}）: {e}")
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
        logger.info("[ADB] ═══ 截图开始: title=%s, file=%s ═══", title or '无', file_name)
        t0 = time.perf_counter()

        if self._take_screenshot_via_exec_out(local_path):
            total_ms = (time.perf_counter() - t0) * 1000
            logger.info("[ADB] ═══ 截图完成 (exec-out): 总耗时=%.0fms ═══", total_ms)
            return str(local_path)

        result = self._take_screenshot_via_remote_file(local_path, file_name)
        total_ms = (time.perf_counter() - t0) * 1000
        if result:
            logger.info("[ADB] ═══ 截图完成 (remote-file): 总耗时=%.0fms ═══", total_ms)
        else:
            logger.error("[ADB] ═══ 截图全部失败: 总耗时=%.0fms ═══", total_ms)
        return result

    # ───────────────────── 录屏 ─────────────────────

    def start_recording(self, output_path: str, max_duration: int | None = None) -> bool:
        """启动 ADB screenrecord 录屏。

        Args:
            output_path: 本地输出视频文件路径（.mp4）
            max_duration: 最大录制时长（秒），默认使用 RECORDING_MAX_DURATION

        Returns:
            是否成功启动
        """
        if self._recording_process is not None:
            # 检查旧进程是否已经结束（异常退出未清理）
            poll = self._recording_process.poll()
            if poll is not None:
                logger.warning("[ADB] 发现残留录屏进程 (exit=%s)，自动清理后重新启动", poll)
                self._recording_process = None
                self._recording_remote_path = None
            else:
                logger.warning("[ADB] 录屏进程仍在运行 (pid=%d)，跳过本次启动", self._recording_process.pid)
                return False

        duration = max_duration or int(getattr(settings, "RECORDING_MAX_DURATION", 180))
        ts = int(time.time() * 1000)
        remote_path = f"/data/local/tmp/recording_{ts}.mp4"
        self._recording_remote_path = remote_path

        cmd = self._adb_command("shell", "screenrecord",
                                "--time-limit", str(duration),
                                "--size", "1280x720",
                                remote_path)
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._recording_process = process
            logger.info("[ADB] 录屏已启动: remote=%s, pid=%d, duration=%ds",
                        remote_path, process.pid, duration)
            return True
        except Exception as e:
            logger.error("[ADB] 启动录屏失败: %s", e)
            self._recording_remote_path = None
            return False

    def stop_recording(self) -> Optional[str]:
        """停止录屏，拉取视频文件到本地并清理设备临时文件。

        Returns:
            本地视频文件路径，如果没有在录屏则返回 None
        """
        process = self._recording_process
        remote_path = self._recording_remote_path
        if process is None or remote_path is None:
            return None

        self._recording_process = None
        self._recording_remote_path = None

        # 发送 SIGTERM 停止 screenrecord
        try:
            process.terminate()
            process.wait(timeout=5)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

        # 等待一小段时间让文件写入完成
        time.sleep(0.5)

        # 拉取文件到本地
        ts = int(time.time() * 1000)
        local_path = settings.RECORDING_DIR / f"recording_{ts}.mp4"
        pull_cmd = self._adb_command("pull", remote_path, str(local_path))
        try:
            result = subprocess.run(
                pull_cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and local_path.exists():
                logger.info("[ADB] 录屏文件已拉取: %s", local_path)
                self._cleanup_remote_file(remote_path)
                return str(local_path)
            else:
                logger.error("[ADB] 拉取录屏文件失败: %s", result.stderr)
        except Exception as e:
            logger.error("[ADB] 拉取录屏文件异常: %s", e)

        self._cleanup_remote_file(remote_path)
        return None

    def read_excel_commands(self, excel_path: str, target_row: Optional[int] = None) -> Dict[str, Any]:
        """读取Excel文件中的命令（带缓存：同一文件未修改时直接返回）"""
        import os
        try:
            mtime = os.path.getmtime(excel_path)
        except OSError:
            mtime = 0.0

        if (self._excel_cache_result is not None
                and self._excel_cache_path == excel_path
                and self._excel_cache_mtime == mtime):
            result = self._excel_cache_result
            # 只切出目标行的 commands，其余复用缓存
            if target_row and target_row <= len(result.get("valid_rows", [])):
                commands = result["valid_rows"][target_row - 1].get("commands", [])
            else:
                commands = result.get("commands", [])
            return {**result, "commands": commands}

        logger.info("[ADB] 读取 Excel: path=%s, target_row=%s", excel_path, target_row or '全部')
        keycode_map = get_keycode_map()
        valid_keys = {str(key).strip().upper() for key in get_runtime_valid_keys() if str(key).strip()}
        console_log(
            f"[read_excel_commands] ASSERT in keycode_map={'ASSERT' in keycode_map}, "
            f"in valid_keys={'ASSERT' in valid_keys}, "
            f"in NON_EXECUTABLE_KEYS={'ASSERT' in NON_EXECUTABLE_KEYS}"
        )
        try:
            df = pd.read_excel(excel_path)

            commands = []
            valid_rows = []
            skipped_rows = []

            if 'preScript' in df.columns:
                console_log("检测到SmartTV模板格式，正在解析preScript列...")

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
                    missing_mapping_keys = set()
                    invalid_keys = set()
                    malformed_commands = []
                    unparsable_commands = []
                    console_log(
                        f"[read_excel_commands] row={index+2} combined_commands={combined_commands}"
                    )
                    for cmd in combined_commands:
                        try:
                            parts = cmd.split('/')
                            if len(parts) == 3:
                                keyname = parts[0].upper()
                                repeat = int(parts[1])
                                delay = float(parts[2])

                                if keyname in keycode_map or keyname in NON_EXECUTABLE_KEYS:
                                    # NON_EXECUTABLE_KEYS（如 ASSERT）即使被外部修改/方案
                                    # 覆盖掉 keycode_map，也保证视为有效命令。
                                    has_valid_command = True
                                elif keyname in valid_keys:
                                    missing_mapping_keys.add(keyname)
                                else:
                                    invalid_keys.add(keyname)
                            else:
                                malformed_commands.append(cmd)
                        except ValueError:
                            unparsable_commands.append(cmd)
                    console_log(
                        f"[read_excel_commands] row={index+2} has_valid={has_valid_command} "
                        f"missing={missing_mapping_keys} invalid={invalid_keys} "
                        f"malformed={malformed_commands} unparsable={unparsable_commands}"
                    )

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
                        if missing_mapping_keys:
                            reason = f"按键缺少键值映射: {', '.join(sorted(missing_mapping_keys))}"
                        elif invalid_keys:
                            reason = f"存在未识别按键: {', '.join(sorted(invalid_keys))}"
                        elif malformed_commands:
                            reason = f"存在格式错误命令: {', '.join(malformed_commands)}"
                        elif unparsable_commands:
                            reason = f"存在无法解析的命令参数: {', '.join(unparsable_commands)}"
                        else:
                            reason = "oriStep和preScript列中没有有效命令"
                        skipped_rows.append({"row": index+2, "reason": reason})

                valid_rows = all_valid_rows
                console_log(f"处理完成：总有效行 {len(valid_rows)} 个")
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
                            if keyname in valid_keys:
                                skipped_rows.append({"row": index+2, "reason": f"keyname '{keyname}' 缺少键值映射"})
                            else:
                                skipped_rows.append({"row": index+2, "reason": f"keyname '{keyname}' 不存在于按键映射表中"})
                            continue

                        cmd_str = f"{keyname}/{repeat}/{delay}"
                        valid_rows.append({"row": index+2, "command": cmd_str})
                    except (ValueError, TypeError) as e:
                        skipped_rows.append({"row": index+2, "reason": f"数据类型错误: {str(e)}"})

            commands = valid_rows[target_row - 1]["commands"] if target_row and target_row <= len(valid_rows) else []

            logger.info("[ADB] Excel 解析完成: 有效行=%d, 跳过=%d, 目标行命令数=%d",
                        len(valid_rows), len(skipped_rows), len(commands))
            if skipped_rows:
                for sr in skipped_rows[:5]:
                    logger.debug("[ADB]   跳过行 %s: %s", sr.get('row'), sr.get('reason'))
                if len(skipped_rows) > 5:
                    logger.debug("[ADB]   ... 还有 %d 行被跳过", len(skipped_rows) - 5)
            result = {
                "commands": commands,
                "valid_rows": valid_rows,
                "skipped_rows": skipped_rows,
                "total_rows": len(valid_rows)
            }
            # 写入缓存
            self._excel_cache_path = excel_path
            self._excel_cache_mtime = mtime
            self._excel_cache_result = result
            return result
        except Exception as e:
            logger.error("[ADB] ✗ Excel 读取失败: %s", e)
            raise Exception(f"读取Excel失败: {e}")
