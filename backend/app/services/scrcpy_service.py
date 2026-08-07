"""scrcpy 串流预览服务。

通过 scrcpy 的 ``--record`` 功能将 H.264 码流以 MP4 容器写入 stdout，
再由 FFmpeg 解码为 JPEG 帧供前端 MJPEG 流消费。

架构：
    [Android] --H.264--> [scrcpy server] --ADB socket--> [scrcpy CLI]
                                                            |
                                                       [FFmpeg pipe]
                                                            |
                                                       [MJPEG 帧]
                                                            |
                                                  [FastAPI MJPEG Stream]
                                                            |
                                                       [浏览器 <img>]
"""

import logging
import os
import subprocess
import time
from threading import Event, Lock, Thread
from typing import Optional

from ..config import settings

logger = logging.getLogger(__name__)

# JPEG SOI / EOI 标记
_JPEG_SOI = b"\xff\xd8"
_JPEG_EOI = b"\xff\xd9"


class ScrcpyService:
    """管理 scrcpy + FFmpeg 子进程，提供 MJPEG 帧缓存。

    设计参考 ``CaptureCardService`` 的共享 JPEG 缓冲架构：
    * 后台线程持续从 FFmpeg stdout 读取 JPEG 帧
    * 最新帧缓存在 ``_latest_jpeg_bytes`` 中
    * 多个 stream 客户端通过 ``wait_for_new_jpeg()`` 无锁并发消费
    * idle timeout 自动释放子进程
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._scrcpy_proc: Optional[subprocess.Popen] = None
        self._ffmpeg_proc: Optional[subprocess.Popen] = None
        self._active_device: Optional[str] = None

        # 帧缓存（与 CaptureCardService 相同的共享缓冲模式）
        self._latest_jpeg_bytes: Optional[bytes] = None
        self._latest_jpeg_at: float = 0.0
        self._encode_lock = Lock()
        self._reader_thread: Optional[Thread] = None
        self._reader_stop_event = Event()
        self._last_consumer_at: float = 0.0

    def _get_scrcpy_path(self) -> str:
        return str(getattr(settings, "SCRCPY_PATH", "scrcpy") or "scrcpy")

    def _get_ffmpeg_path(self) -> str:
        return str(getattr(settings, "FFMPEG_PATH", "ffmpeg") or "ffmpeg")

    def _get_max_size(self) -> int:
        return int(getattr(settings, "SCRCPY_MAX_SIZE", 1024))

    def _get_max_fps(self) -> int:
        return int(getattr(settings, "SCRCPY_MAX_FPS", 30))

    def _get_video_codec(self) -> str:
        return str(getattr(settings, "SCRCPY_VIDEO_CODEC", "h264") or "h264")

    def _get_jpeg_quality(self) -> int:
        """FFmpeg MJPEG 质量参数（1-31，越小质量越高）。"""
        return max(1, min(31, int(getattr(settings, "SCRCPY_JPEG_QUALITY", 80))))

    def _get_idle_timeout(self) -> float:
        return float(getattr(settings, "SCRCPY_IDLE_TIMEOUT", 10.0))

    def _release_unlocked(self) -> None:
        """停止 reader 线程和所有子进程。"""
        self._reader_stop_event.set()

        if self._reader_thread is not None and self._reader_thread.is_alive():
            try:
                self._reader_thread.join(timeout=2.0)
            except RuntimeError:
                pass
        self._reader_thread = None

        for proc_attr in ("_ffmpeg_proc", "_scrcpy_proc"):
            proc = getattr(self, proc_attr)
            if proc is None:
                continue
            try:
                if proc.poll() is None:
                    # Windows 下 terminate() 发送 CTRL_BREAK_EVENT 可能不够，
                    # 先尝试 terminate，超时后 kill
                    proc.terminate()
                    try:
                        proc.wait(timeout=3.0)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=2.0)
            except Exception:
                pass
            setattr(self, proc_attr, None)

        with self._encode_lock:
            self._latest_jpeg_bytes = None
            self._latest_jpeg_at = 0.0

        self._active_device = None

    def release(self) -> None:
        """释放 scrcpy 和 FFmpeg 子进程。"""
        with self._lock:
            self._release_unlocked()

    def is_running(self) -> bool:
        """scrcpy + FFmpeg 进程组是否都在运行。"""
        return (
            self._scrcpy_proc is not None
            and self._scrcpy_proc.poll() is None
            and self._ffmpeg_proc is not None
            and self._ffmpeg_proc.poll() is None
        )

    def _ensure_running_unlocked(self, device_serial: str) -> None:
        """确保 scrcpy + FFmpeg 正在为目标设备运行。如果设备已切换则重启。"""
        if self.is_running() and self._active_device == device_serial:
            return

        # 设备已切换或进程已退出，重启
        self._release_unlocked()
        self._start_pipeline(device_serial)

    def _start_pipeline(self, device_serial: str) -> None:
        """启动 scrcpy --record=pipe:1 | ffmpeg 管道。"""
        scrcpy_path = self._get_scrcpy_path()
        ffmpeg_path = self._get_ffmpeg_path()
        max_size = self._get_max_size()
        max_fps = self._get_max_fps()
        codec = self._get_video_codec()
        no_audio = getattr(settings, "SCRCPY_NO_AUDIO", True)
        jpeg_quality = self._get_jpeg_quality()

        # 构建 scrcpy 命令
        scrcpy_cmd = [
            scrcpy_path,
            "-s", device_serial,
            "--no-window",
            "--max-size", str(max_size),
            "--max-fps", str(max_fps),
            "--video-codec", codec,
            "--record", "pipe:1",
        ]
        if no_audio:
            scrcpy_cmd.append("--no-audio")

        # 构建 FFmpeg 命令：从 stdin 读取 MP4 容器，输出逐帧 JPEG
        ffmpeg_cmd = [
            ffmpeg_path,
            "-probesize", "32",
            "-analyzeduration", "0",
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-i", "pipe:0",
            "-f", "image2pipe",
            "-vcodec", "mjpeg",
            "-q:v", str(jpeg_quality),
            "-vf", f"scale={max_size}:-2",
            "pipe:1",
        ]

        logger.info("[scrcpy] 启动管道: %s | %s", " ".join(scrcpy_cmd), " ".join(ffmpeg_cmd))

        try:
            # 启动 scrcpy，stdout 作为 FFmpeg 的 stdin
            self._scrcpy_proc = subprocess.Popen(
                scrcpy_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )

            # 启动 FFmpeg，stdin 来自 scrcpy 的 stdout
            self._ffmpeg_proc = subprocess.Popen(
                ffmpeg_cmd,
                stdin=self._scrcpy_proc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )

            # scrcpy 的 stdout 已经被 FFmpeg 读取，释放 scrcpy 端的引用避免管道死锁
            # 注意：不能关闭 scrcpy_proc.stdout，否则 FFmpeg 读到 EOF
            # 但需要确保 scrcpy 不会因为 FFmpeg 退出而收到 SIGPIPE
        except FileNotFoundError as exc:
            logger.error("[scrcpy] 启动失败，找不到可执行文件: %s", exc)
            self._release_unlocked()
            raise RuntimeError(f"找不到 scrcpy 或 FFmpeg，请确认已安装并在 PATH 中: {exc}") from exc
        except Exception as exc:
            logger.error("[scrcpy] 启动失败: %s", exc)
            self._release_unlocked()
            raise

        self._active_device = device_serial
        self._reader_stop_event.clear()
        self._reader_thread = Thread(
            target=self._reader_loop,
            name="scrcpy-reader",
            daemon=True,
        )
        self._reader_thread.start()
        logger.info("[scrcpy] 管道已启动，设备: %s", device_serial)

    def _reader_loop(self) -> None:
        """后台线程：从 FFmpeg stdout 逐帧读取 JPEG，更新共享缓冲。"""
        ffmpeg_proc = self._ffmpeg_proc
        if ffmpeg_proc is None or ffmpeg_proc.stdout is None:
            return

        stdout = ffmpeg_proc.stdout
        idle_timeout = self._get_idle_timeout()
        buffer = b""

        while not self._reader_stop_event.is_set():
            # 检查进程是否还在运行
            if ffmpeg_proc.poll() is not None:
                logger.warning("[scrcpy] FFmpeg 进程已退出 (code=%s)", ffmpeg_proc.returncode)
                break

            try:
                chunk = stdout.read(65536)
            except (ValueError, OSError):
                break
            if not chunk:
                break

            buffer += chunk

            # 从 buffer 中提取完整的 JPEG 帧
            while True:
                soi_pos = buffer.find(_JPEG_SOI)
                if soi_pos < 0:
                    # 没有 SOI，丢弃已积累的垃圾数据
                    buffer = b""
                    break

                eoi_pos = buffer.find(_JPEG_EOI, soi_pos + 2)
                if eoi_pos < 0:
                    # SOI 后面还没找到 EOI，等待更多数据
                    # 保留从 SOI 开始的数据
                    buffer = buffer[soi_pos:]
                    break

                # 提取完整 JPEG 帧
                jpeg_frame = buffer[soi_pos: eoi_pos + 2]
                buffer = buffer[eoi_pos + 2:]

                now = time.perf_counter()
                with self._encode_lock:
                    self._latest_jpeg_bytes = jpeg_frame
                    self._latest_jpeg_at = now

                # idle timeout 检测
                last_consumer = self._last_consumer_at
                if last_consumer and (time.time() - last_consumer) > idle_timeout:
                    if (time.time() - self._last_consumer_at) > idle_timeout:
                        logger.info("[scrcpy] idle timeout，自动释放")
                        self._reader_stop_event.set()
                        return

        logger.info("[scrcpy] reader 线程退出")

    def wait_for_new_jpeg(self, last_frame_at: float, timeout: float = 1.0):
        """供 stream 路由调用：阻塞直到出现一帧不同于 ``last_frame_at`` 的 JPEG。

        与 CaptureCardService.wait_for_new_jpeg() 接口一致，多客户端可并发调用。
        """
        device = self._active_device
        if device is None:
            raise RuntimeError("scrcpy 未启动，请先选择设备")

        with self._lock:
            self._ensure_running_unlocked(device)

        self._last_consumer_at = time.time()

        deadline = time.perf_counter() + timeout
        while True:
            with self._encode_lock:
                jpeg_bytes = self._latest_jpeg_bytes
                jpeg_perf = self._latest_jpeg_at
            if jpeg_bytes is not None and jpeg_perf != last_frame_at:
                self._last_consumer_at = time.time()
                return jpeg_bytes, jpeg_perf, {"source": "scrcpy", "device": device}

            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                if jpeg_bytes is None:
                    raise RuntimeError("scrcpy 串流超时，未能获取到画面")
                self._last_consumer_at = time.time()
                return jpeg_bytes, jpeg_perf, {"source": "scrcpy", "device": device}

            time.sleep(min(0.01, remaining))

    def capture_encoded_frame(self) -> dict:
        """获取最新一帧 JPEG（供首次连接使用）。"""
        device = self._active_device
        if device is None:
            raise RuntimeError("scrcpy 未启动，请先选择设备")

        with self._lock:
            self._ensure_running_unlocked(device)

        self._last_consumer_at = time.time()

        # 等待首帧
        deadline = time.perf_counter() + 5.0
        while True:
            with self._encode_lock:
                jpeg_bytes = self._latest_jpeg_bytes
                jpeg_perf = self._latest_jpeg_at
            if jpeg_bytes is not None:
                return {
                    "bytes": jpeg_bytes,
                    "source": "scrcpy",
                    "device": device,
                    "captured_at": int(time.time() * 1000),
                }
            if time.perf_counter() >= deadline:
                raise RuntimeError("scrcpy 串流超时，未能获取到首帧")
            time.sleep(0.02)

    def get_status(self) -> dict:
        """返回当前 scrcpy 服务状态。"""
        return {
            "running": self.is_running(),
            "device": self._active_device,
            "has_frame": self._latest_jpeg_bytes is not None,
        }


scrcpy_service = ScrcpyService()
