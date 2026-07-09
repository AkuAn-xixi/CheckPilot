"""采集卡预览服务。"""
import logging
import os
import threading
import time
from threading import Event, Lock, Thread
from typing import Optional

import cv2
import numpy as np

from ..config import settings

logger = logging.getLogger(__name__)


class CaptureCardService:
    """使用 OpenCV 从采集卡读取设备画面。

    为了维持 60fps 这种高帧率：

    * 用一个后台线程持续 ``cap.read()`` 把"最新一帧"放在共享变量里
    * 单帧请求 / 实时流都从共享变量取，避免互相竞争 capture
    * 设置 ``CAP_PROP_FOURCC`` 优先走 MJPG，避开 USB2 上 YUY2 拉到 30fps 的限制
    * 默认禁用 ``CAP_PROP_CONVERT_RGB`` 之外的转换，保持驱动直出
    """

    DEVICE_SCAN_RANGE = 10
    READER_IDLE_TIMEOUT = 8.0  # 多久没人来取就把 capture / 线程释放掉

    def __init__(self) -> None:
        self._cap = None
        self._cap_device_id = None
        self._active_device_id: Optional[int] = None
        self._active_device_label: str = ""
        self._lock = Lock()

        # 后台抓帧线程相关
        self._reader_thread: Optional[Thread] = None
        self._reader_stop_event = Event()
        self._latest_frame = None
        self._latest_frame_lock = Lock()
        self._latest_frame_at: float = 0.0
        self._latest_frame_event = Event()
        self._last_consumer_at: float = 0.0
        # 编码端共享缓冲，避免每个 stream 独立编码同一帧
        self._latest_jpeg_bytes: Optional[bytes] = None
        self._latest_jpeg_at: float = 0.0
        self._encode_lock = Lock()

        # 录屏相关
        self._recording_writer = None  # cv2.VideoWriter 或 imageio writer
        self._recording_thread: Optional[Thread] = None
        self._recording_stop_event = Event()
        self._recording_path: Optional[str] = None
        self._recording_active: bool = False
        self._recording_use_imageio: bool = False

    def _get_default_device_id(self) -> int:
        return int(settings.CAPTURE_CARD_DEVICE_ID)

    def _get_device_id(self) -> int:
        if self._active_device_id is None:
            self._restore_active_device_from_disk()
        if self._active_device_id is not None:
            return int(self._active_device_id)
        return self._get_default_device_id()

    def _restore_active_device_from_disk(self) -> None:
        # 延迟导入，避免循环依赖（runtime 也会 import 本服务）。
        from ..runtime import get_capture_card_device

        persisted = get_capture_card_device()
        if not persisted:
            return
        device_id = persisted.get("device_id")
        if isinstance(device_id, int):
            self._active_device_id = device_id
            label = persisted.get("label")
            self._active_device_label = str(label or "")

    def _get_api_preference(self) -> int:
        if os.name == "nt" and hasattr(cv2, "CAP_DSHOW"):
            return cv2.CAP_DSHOW
        return getattr(cv2, "CAP_ANY", 0)

    def _build_capture_metadata(self, captured_at: int) -> dict:
        device_id = self._get_device_id()
        label = self._active_device_label.strip() if self._active_device_label else ""
        return {
            "captured_at": captured_at,
            "label": label or f"采集卡 {device_id}",
            "device_id": device_id,
        }

    def _release_unlocked(self) -> None:
        # 停止录屏
        if self._recording_writer is not None:
            self._recording_stop_event.set()
            if self._recording_thread is not None and self._recording_thread.is_alive():
                try:
                    self._recording_thread.join(timeout=2.0)
                except RuntimeError:
                    pass
            try:
                if self._recording_use_imageio:
                    self._recording_writer.close()
                else:
                    self._recording_writer.release()
            except Exception:
                pass
            self._recording_writer = None
            self._recording_thread = None
            self._recording_path = None
            self._recording_active = False
            self._recording_use_imageio = False

        # 停后台读帧线程
        self._reader_stop_event.set()
        if self._reader_thread is not None and self._reader_thread.is_alive():
            try:
                self._reader_thread.join(timeout=1.0)
            except RuntimeError:
                pass
        self._reader_thread = None
        with self._latest_frame_lock:
            self._latest_frame = None
            self._latest_frame_at = 0.0
        with self._encode_lock:
            self._latest_jpeg_bytes = None
            self._latest_jpeg_at = 0.0

        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
        self._cap = None
        self._cap_device_id = None

    def release(self) -> None:
        with self._lock:
            self._release_unlocked()

    @staticmethod
    def _fourcc_from_str(value: str) -> Optional[int]:
        text = (value or "").strip().upper()
        if not text or len(text) != 4:
            return None
        try:
            return cv2.VideoWriter_fourcc(*text)
        except Exception:
            return None

    def _open_capture_unlocked(self):
        self._release_unlocked()
        self._reader_stop_event = Event()  # 重新创建，前一次 release 已 set 过

        device_id = self._get_device_id()
        cap = cv2.VideoCapture(device_id, self._get_api_preference())
        if not cap or not cap.isOpened():
            if cap is not None:
                cap.release()
            raise RuntimeError(f"无法打开采集卡设备: {device_id}")

        # 优先设 FourCC（影响驱动输出的像素格式 + 带宽，必须在分辨率/帧率之前）
        fourcc_value = self._fourcc_from_str(getattr(settings, "CAPTURE_CARD_FOURCC", ""))
        if fourcc_value is not None:
            try:
                cap.set(cv2.CAP_PROP_FOURCC, fourcc_value)
            except Exception:
                pass

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(settings.CAPTURE_CARD_WIDTH))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(settings.CAPTURE_CARD_HEIGHT))
        cap.set(cv2.CAP_PROP_FPS, int(settings.CAPTURE_CARD_FPS_TARGET))
        if hasattr(cv2, "CAP_PROP_BUFFERSIZE"):
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self._cap = cap
        self._cap_device_id = device_id

        # 启动后台读帧线程，保证最新帧总是在共享缓冲里
        self._reader_thread = Thread(
            target=self._reader_loop,
            name="capture-card-reader",
            daemon=True,
        )
        self._reader_thread.start()

    def _reader_loop(self) -> None:
        idle_after = max(2.0, float(self.READER_IDLE_TIMEOUT))
        # 抓不到帧时小等一下，避免空转占 CPU
        backoff = 0.0
        encode_quality = max(1, min(100, int(getattr(settings, "CAPTURE_CARD_JPEG_QUALITY", 75))))
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), encode_quality]
        while not self._reader_stop_event.is_set():
            cap = self._cap
            if cap is None:
                break

            try:
                ok, frame = cap.read()
            except Exception:
                ok, frame = False, None

            now = time.perf_counter()
            if ok and frame is not None:
                with self._latest_frame_lock:
                    self._latest_frame = frame
                    self._latest_frame_at = now
                # 抓到一帧立即编码一次缓存起来。所有 stream 客户端直接读缓冲，
                # 既不需要互相争锁，也不会重复编码同一帧。
                try:
                    encoded_ok, encoded = cv2.imencode(".jpg", frame, encode_params)
                except Exception:
                    encoded_ok = False
                    encoded = None
                if encoded_ok and encoded is not None:
                    with self._encode_lock:
                        self._latest_jpeg_bytes = encoded.tobytes()
                        self._latest_jpeg_at = now
                self._latest_frame_event.set()
                backoff = 0.0
            else:
                # 读失败：等极短时间重试一次；连续失败说明 capture 已经断了
                backoff = min(0.05, backoff + 0.005)
                if self._reader_stop_event.wait(backoff):
                    break

            # 录屏期间不释放采集卡
            if self._recording_active:
                continue
            # 长时间没有消费者就主动停掉抓帧，避免空跑占用采集卡
            last_consumer = self._last_consumer_at
            if last_consumer and (time.time() - last_consumer) > idle_after:
                with self._lock:
                    # 二次确认仍然没人在用
                    if (time.time() - self._last_consumer_at) > idle_after:
                        # 触发 release 走出循环
                        self._reader_stop_event.set()
                        # 清掉 cap 让外层下次访问重新打开
                        try:
                            self._cap.release()
                        except Exception:
                            pass
                        self._cap = None
                        self._cap_device_id = None
                        break

    def _ensure_capture_unlocked(self):
        device_id = self._get_device_id()
        cap_alive = self._cap is not None and self._cap.isOpened()
        thread_alive = self._reader_thread is not None and self._reader_thread.is_alive()
        if cap_alive and thread_alive and self._cap_device_id == device_id:
            return
        self._open_capture_unlocked()

    def _wait_latest_frame_unlocked(self, timeout: float = 1.5):
        """阻塞等待后台线程产出第一帧（或拿到一个新帧）。

        不依赖 Event 通知（多消费者下会被 wait_for_new_jpeg 抢去 clear），
        而是轮询 ``self._latest_frame``。50ms 一次足够覆盖 60fps 出帧速率。
        """
        self._ensure_capture_unlocked()
        deadline = time.perf_counter() + max(0.0, float(timeout))
        while True:
            with self._latest_frame_lock:
                frame = self._latest_frame
                captured_perf = self._latest_frame_at
            if frame is not None:
                return frame, captured_perf
            if time.perf_counter() >= deadline:
                raise RuntimeError(f"采集卡设备 {self._get_device_id()} 读取画面超时")
            time.sleep(0.02)

    def capture_frame(self) -> dict:
        with self._lock:
            frame, _ = self._wait_latest_frame_unlocked()
            self._last_consumer_at = time.time()
            captured_at = int(time.time() * 1000)
            return {
                "frame": frame.copy(),  # 拷贝一份，避免读取时后台线程覆盖
                **self._build_capture_metadata(captured_at),
            }

    def capture_encoded_frame(self, extension: str = ".jpg") -> dict:
        """优先返回缓存的最新 JPEG，避免每个 stream 都重复编码同一帧。"""
        ext = (extension or ".jpg").lower()
        if ext != ".jpg":
            # 非 jpg 走老路径
            result = self.capture_frame()
            ok, encoded = cv2.imencode(extension, result["frame"])
            if not ok:
                raise RuntimeError("编码采集卡画面失败")
            return {
                "bytes": encoded.tobytes(),
                **{key: value for key, value in result.items() if key != "frame"},
            }

        with self._lock:
            frame, captured_perf = self._wait_latest_frame_unlocked()
            self._last_consumer_at = time.time()
            metadata = self._build_capture_metadata(int(time.time() * 1000))

        with self._encode_lock:
            if self._latest_jpeg_bytes is not None and self._latest_jpeg_at == captured_perf:
                # 同一帧已经编码过，直接复用
                return {"bytes": self._latest_jpeg_bytes, **metadata}

            quality = max(1, min(100, int(getattr(settings, "CAPTURE_CARD_JPEG_QUALITY", 75))))
            params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
            ok, encoded = cv2.imencode(".jpg", frame, params)
            if not ok:
                raise RuntimeError("编码采集卡画面失败")

            jpeg_bytes = encoded.tobytes()
            self._latest_jpeg_bytes = jpeg_bytes
            self._latest_jpeg_at = captured_perf
            return {"bytes": jpeg_bytes, **metadata}

    def wait_for_new_jpeg(self, last_frame_at: float, timeout: float = 1.0):
        """供 stream 路由调用：阻塞直到出现一帧不同于 ``last_frame_at`` 的画面。

        多个 stream 客户端可以并发调用本方法；它**不会**抢 ``self._lock``，因为
        reader 线程在抓到帧时就已经把 JPEG 缓冲准备好。客户端只需用
        ``self._latest_frame_event`` 等到新帧 + 直接读 ``self._latest_jpeg_bytes``。
        """
        # 第一次连接时，画面可能还没启动；做一次 ensure 把 capture 打开
        if self._cap is None or not self._cap.isOpened():
            with self._lock:
                self._ensure_capture_unlocked()

        self._last_consumer_at = time.time()

        deadline = time.perf_counter() + timeout
        while True:
            with self._encode_lock:
                jpeg_bytes = self._latest_jpeg_bytes
                jpeg_perf = self._latest_jpeg_at
            if jpeg_bytes is not None and jpeg_perf != last_frame_at:
                self._last_consumer_at = time.time()
                metadata = self._build_capture_metadata(int(time.time() * 1000))
                return jpeg_bytes, jpeg_perf, metadata

            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                # 超时仍然返回当前最新一帧，避免长时间无输出
                if jpeg_bytes is None:
                    raise RuntimeError(f"采集卡设备 {self._get_device_id()} 读取画面超时")
                self._last_consumer_at = time.time()
                metadata = self._build_capture_metadata(int(time.time() * 1000))
                return jpeg_bytes, jpeg_perf, metadata

            # 短暂 sleep 让 reader 产出新帧再轮询。不使用 Event.clear() 避免多消费者竞争，
            # 50ms 检查一次足够支撑 60fps 出帧（每 16ms 一帧，平均 8ms 内能拿到）
            time.sleep(min(0.01, remaining))

    def capture_preview(self, file_name: str = "") -> dict:
        result = self.capture_frame()
        if not file_name:
            file_name = f"device_preview_capture_card_{self._get_device_id()}.png"
        elif not file_name.endswith(".png"):
            file_name += ".png"
        target_path = settings.SCREENSHOT_DIR / file_name

        target_path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(target_path), result["frame"]):
            raise RuntimeError("保存采集卡画面失败")

        return {
            "path": str(target_path),
            **{key: value for key, value in result.items() if key != "frame"},
        }

    # ───────────────────── 设备枚举 / 切换 ─────────────────────

    def _list_dshow_device_names(self) -> Optional[list[str]]:
        """Windows DirectShow 真实设备名列表。

        OpenCV 索引和系统枚举顺序经常不一致，而且打开失败的索引判定不稳定，
        导致用户的 OBS 虚拟摄像头 / USB 采集卡在某些时刻会被漏检。这里优先
        通过 ``pygrabber`` 拿到 DirectShow 真实设备名，按枚举顺序当成 OpenCV
        ``device_id``。``pygrabber`` 缺失时返回 ``None`` 让上层回退到索引扫描。
        """
        if os.name != "nt":
            return None
        try:
            from pygrabber.dshow_graph import FilterGraph
        except Exception:
            return None
        try:
            return list(FilterGraph().get_input_devices())
        except Exception:
            return None

    def _probe_device(self, device_id: int, api_preference: int, total_timeout: float = 1.5) -> bool:
        """尝试打开一个索引：能成功打开就视为可用，再尽量等到第一帧。

        某些采集卡（特别是 USB3 HDMI 卡和 OBS 虚拟摄像头）冷启动时，
        ``cap.read()`` 第一帧需要 500ms~1s 才返回。原先单次 read 失败就把它
        判为"不可用"，会漏掉这些设备。这里改成"isOpened() 即可用 + 尽量
        在 ``total_timeout`` 内再等到一帧"。
        """
        cap = None
        try:
            cap = cv2.VideoCapture(device_id, api_preference)
            if not cap or not cap.isOpened():
                return False
            # 已经能打开就当作可用；下面的 read 只是尽力获取一帧热身
            deadline = time.perf_counter() + max(0.0, float(total_timeout))
            while time.perf_counter() < deadline:
                ok, frame = cap.read()
                if ok and frame is not None:
                    return True
                time.sleep(0.05)
            return True
        except Exception:
            return False
        finally:
            try:
                if cap is not None:
                    cap.release()
            except Exception:
                pass

    def list_capture_devices(self) -> list[dict]:
        """枚举本机当前可用的视频采集设备。

        Windows 优先用 DirectShow 列出真实设备名；其它平台或 ``pygrabber``
        缺失时回退到 OpenCV 索引扫描。
        """
        api_preference = self._get_api_preference()

        # 暂时释放当前已开的 capture，避免独占同一索引导致探测失败。
        # 释放后给驱动一点缓冲时间真正放掉句柄，否则紧接着的探测会失败。
        with self._lock:
            self._release_unlocked()
        time.sleep(0.2)

        names = self._list_dshow_device_names()
        if names is not None:
            return [
                {"device_id": index, "label": name or f"采集卡 {index}"}
                for index, name in enumerate(names)
            ]

        results: list[dict] = []
        for device_id in range(self.DEVICE_SCAN_RANGE):
            if not self._probe_device(device_id, api_preference):
                continue
            results.append({
                "device_id": device_id,
                "label": f"采集卡 {device_id}",
            })
        return results

    def get_active_device(self) -> dict:
        """返回当前生效的采集卡 device_id / label / 是否来自持久化字段。"""
        if self._active_device_id is None:
            self._restore_active_device_from_disk()

        device_id = self._get_device_id()
        is_explicit = self._active_device_id is not None
        return {
            "device_id": device_id,
            "label": (self._active_device_label.strip() or f"采集卡 {device_id}"),
            "is_explicit": is_explicit,
        }

    def set_active_device(self, device_id: int, label: str | None = None) -> dict:
        """切换采集卡设备并写盘。失败时维持原状态。"""
        try:
            normalized_id = int(device_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("device_id 必须是整数") from exc

        normalized_label = str(label or "").strip()

        # 提前探测一下，给前端可解释的错误而不是等到后续 capture_frame 才报错。
        # 切换前先释放上一个 capture 句柄，给驱动一点缓冲时间再探测，
        # 否则部分采集卡会因为"独占未释放"导致这次探测失败。
        api_preference = self._get_api_preference()
        with self._lock:
            self._release_unlocked()
        time.sleep(0.2)

        if not self._probe_device(normalized_id, api_preference):
            raise RuntimeError(f"无法打开采集卡设备: {normalized_id}")

        from ..runtime import set_capture_card_device

        with self._lock:
            self._active_device_id = normalized_id
            self._active_device_label = normalized_label

        set_capture_card_device({
            "device_id": normalized_id,
            "label": normalized_label,
        })
        return self.get_active_device()

    # ───────────────────── 录屏 ─────────────────────

    def _recording_loop(self, writer: cv2.VideoWriter, fps: float) -> None:
        """后台线程：持续从 _latest_frame 读取帧并写入 VideoWriter。"""
        frame_interval = 1.0 / max(1.0, fps)
        last_written_at = 0.0
        while not self._recording_stop_event.is_set():
            with self._latest_frame_lock:
                frame = self._latest_frame
                frame_at = self._latest_frame_at
            # 只写新帧，避免重复写同一帧；拷贝一份防止 reader 线程覆盖
            if frame is not None and frame_at != last_written_at:
                try:
                    writer.write(frame.copy())
                except Exception:
                    pass
                last_written_at = frame_at
                # 更新消费者时间戳，防止 reader_loop 自动释放采集卡
                self._last_consumer_at = time.time()
            self._recording_stop_event.wait(frame_interval)

    def start_recording(self, output_path: str, fps: int | None = None) -> bool:
        """启动采集卡录屏。

        Args:
            output_path: 输出视频文件路径（.mp4）
            fps: 录屏帧率，默认使用 CAPTURE_CARD_RECORDING_FPS

        Returns:
            是否成功启动
        """
        if self._recording_writer is not None:
            return False

        target_fps = fps or int(getattr(settings, "CAPTURE_CARD_RECORDING_FPS", 30))

        # 先清 stop_event，再 ensure_capture（ensure 内部会检查 stop_event）
        self._reader_stop_event.clear()

        # 确保采集卡已打开，且 reader 线程在跑
        with self._lock:
            self._ensure_capture_unlocked()

        # 等待第一帧获取分辨率
        try:
            with self._lock:
                frame, _ = self._wait_latest_frame_unlocked(timeout=5.0)
        except RuntimeError:
            logger.error("[采集卡] 录屏启动失败：等待首帧超时")
            return False

        h, w = frame.shape[:2]
        # 使用 OpenCV 录制（速度快），后续异步转换为 H.264
        writer = None
        actual_path = output_path
        for fourcc_str, ext in [
            ("mp4v", ".mp4"),
            ("MJPG", ".avi"),
            ("XVID", ".avi"),
        ]:
            fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
            path = output_path if ext == ".mp4" else output_path.rsplit('.', 1)[0] + ext
            writer = cv2.VideoWriter(path, fourcc, float(target_fps), (w, h))
            if writer.isOpened():
                actual_path = path
                logger.info("[采集卡] VideoWriter 使用编码器: %s -> %s", fourcc_str, path)
                break
            writer.release()
            writer = None
        if writer is None:
            logger.error("[采集卡] 录屏启动失败：所有编码器都打不开")
            return False

        # 更新消费者时间戳，防止录屏期间 reader_loop 自动释放采集卡
        self._last_consumer_at = time.time()
        self._recording_active = True
        self._recording_stop_event = Event()
        self._recording_writer = writer
        self._recording_path = actual_path
        self._recording_use_imageio = False
        self._recording_thread = Thread(
            target=self._recording_loop,
            args=(writer, float(target_fps)),
            name="capture-card-recorder",
            daemon=True,
        )
        self._recording_thread.start()
        logger.info("[采集卡] 录屏已启动: %s (%dx%d @ %dfps)", actual_path, w, h, target_fps)
        return True

    def stop_recording(self) -> Optional[str]:
        """停止录屏并返回视频文件路径（原始格式）。

        Returns:
            视频文件路径，如果没有在录屏则返回 None
        """
        if self._recording_writer is None:
            return None

        self._recording_stop_event.set()
        if self._recording_thread is not None and self._recording_thread.is_alive():
            self._recording_thread.join(timeout=3.0)
        self._recording_thread = None
        self._recording_active = False

        try:
            self._recording_writer.release()
        except Exception:
            pass
        self._recording_writer = None

        result_path = self._recording_path
        self._recording_path = None
        return result_path

    def stop_recording_and_convert(self) -> Optional[str]:
        """停止录屏（精简版：不进行格式转换，直接返回原始文件路径）。

        Returns:
            视频文件路径，如果没有在录屏则返回 None
        """
        return self.stop_recording()


capture_card_service = CaptureCardService()