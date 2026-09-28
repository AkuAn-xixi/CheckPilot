"""ASR 资源探测与运行服务模块"""
import importlib
import importlib.util
import json
import logging
import math
import os
import re
import shutil
import sys
import wave
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np
from fastapi import UploadFile

from ..config import settings

_log = logging.getLogger(__name__)


class AsrRuntimeError(RuntimeError):
    """Raised when ASR runtime dependencies or execution are unavailable."""


# ──────────────────────────────────────────────────────────────────────────────
# Backend 抽象
#
# 不同的 ASR 模型加载与推理流程差异较大（Qwen3-ASR 用 ``qwen_asr.Qwen3ASRModel``，
# Cohere Transcribe 用 ``transformers.AutoModelForSpeechSeq2Seq``）。把这部分细节
# 收敛到 ``AsrBackend`` 协议中，``AsrService`` 只负责模型目录管理与缓存。
# ──────────────────────────────────────────────────────────────────────────────

#: 模型目录里写入的元信息文件名，记录该目录归属哪一种后端、关联仓库等。
BACKEND_META_FILENAME = "backend_meta.json"

#: 两种后端类型常量
BACKEND_KIND_QWEN = "qwen"
BACKEND_KIND_COHERE = "cohere"
BACKEND_KIND_UNKNOWN = "unknown"

#: Cohere Transcribe 默认参数（HuggingFace Hub 仓库与目标采样率）
COHERE_DEFAULT_MODEL_NAME = "Cohere-Transcribe-03-2026"
COHERE_DEFAULT_REPO_ID = "CohereLabs/cohere-transcribe-03-2026"
COHERE_TARGET_SAMPLE_RATE = 16000

#: Qwen3-ASR context 热词词表文件（与 asr_text_substitutions.json 同目录同命运；
#: 每行一个词/短语，# 开头为注释行，保存后下一次识别自动生效，无需重启）
ASR_HOTWORDS_FILENAME = "asr_hotwords.txt"
#: context 词表上限：词条数 / 单条字符数（防 prompt 膨胀）
MAX_CONTEXT_WORDS = 100
MAX_CONTEXT_WORD_CHARS = 50
#: context 提示串前缀（Qwen3-ASR 生态通用词汇偏置写法）
CONTEXT_PROMPT_PREFIX = "Vocabulary: "
#: 静音判定上限（RMS，幅度已归一到 [-1, 1]）：低于此值视为没录到语音，跳过识别。
#: 实测有效录音 RMS ≈ 1e-2、采集掉线时为 4e-5，两者相差 300 倍，
#: 阈值取中间量级（≈ -60 dBFS）即可稳定区分，不会误伤正常录音。
SILENT_AUDIO_RMS_FLOOR = 1e-3
#: 提示串复读判定的最少段数：识别结果被标点切出这么多段、且每段都是热词时，
#: 才认定模型在复读 context（避开 "HOME" 这类单词用例的误判）
PROMPT_ECHO_MIN_SEGMENTS = 3
#: 识别不可用的原因，随结果回传给调用方写进界面与结果文件：
#: 这两种情况都没有可信识别文本，结论应记 NO_REF（无法判定）而非 FAIL
TRANSCRIPT_SILENT_REASON = "录音为静音，未捕获到语音"
TRANSCRIPT_ECHO_REASON = "识别结果复读了热词提示串"

#: 音量归一化的增益区间。上限放宽到 200 倍以覆盖采集卡等极弱信号（-60dB 级）
#: 录音，否则归一化后仍停留在 -50dB 附近无法识别。
NORMALIZATION_GAIN_MIN = 0.1
NORMALIZATION_GAIN_MAX = 200.0
#: 人声频段增强：带通范围与叠加增益（300Hz-3kHz 是人声主要能量区）
VOICE_BAND_LOW_HZ = 300
VOICE_BAND_HIGH_HZ = 3000
VOICE_BAND_BOOST = 0.3
#: 采样率低于此值时跳过人声频段增强（Nyquist 已低于 3kHz，滤波无意义）
VOICE_BOOST_MIN_SAMPLE_RATE = 6000
#: 本底噪声低于此值（dBFS）时跳过降噪：16bit 量化极限约 -90.3dBFS，采集卡
#: 数字直采的底噪就贴在它附近，说明录音里根本没有噪声，只有量化底噪。
#: 此时非平稳门控会逐帧追着量化噪声开合，实测每遍改动 16% 信号能量且不收敛、
#: 还吃掉 1dB 电平，27 条真实录音对照显示多降一遍平均分 99.20% → 96.19%。
#: 阈值取 -80dBFS：远高于量化极限，又远低于任何真实环境噪声（通常 -60dBFS 以上）。
NOISE_FLOOR_SKIP_DBFS = -80.0
#: 本底噪声估计：分帧长度（秒）与所取分位数（语音只占一小部分，最安静的那批
#: 帧反映的就是本底，不受说话人音量影响）。
NOISE_FLOOR_FRAME_SECONDS = 0.02
NOISE_FLOOR_PERCENTILE = 10

COHERE_LANGUAGE_ALIASES = {
    "english": "en", "en": "en", "en-us": "en",
    "german": "de", "de": "de",
    "french": "fr", "fr": "fr",
    "italian": "it", "it": "it",
    "spanish": "es", "es": "es",
    "portuguese": "pt", "pt": "pt",
    "greek": "el", "el": "el",
    "dutch": "nl", "nl": "nl",
    "polish": "pl", "pl": "pl",
    "vietnamese": "vi", "vi": "vi",
    "chinese": "zh", "zh": "zh", "zh-cn": "zh",
    "arabic": "ar", "ar": "ar",
    "japanese": "ja", "ja": "ja",
    "korean": "ko", "ko": "ko",
}

#: 通过 HuggingFace 镜像下载时的端点候选，仅使用国内镜像。
DEFAULT_HF_DOWNLOAD_ENDPOINT = "https://hf-mirror.com"
# 国内备选镜像源列表（按优先级排序）
HF_MIRROR_ENDPOINTS = [
    "https://hf-mirror.com",
    "https://huggingface.sukaka.top",
    "https://hf.xxxx.one",
]


@dataclass(frozen=True)
class TranscriptionResult:
    """一次 ASR 识别的结果。

    把「识别不出可信文本」和「识别出一段文本」区分开：前者不能让空的识别
    文本流进比对（会被算成 0 分 FAIL，把采集/模型故障记成设备不达标），
    所以连原因一起回传，由调用方记 NO_REF。

    Attributes:
        text: 识别文本；识别不可用时为空串。
        unavailable_reason: 识别不可用的原因（静音 / 复读热词提示串）；
            识别正常时为空串。
    """

    text: str = ""
    unavailable_reason: str = ""

    @property
    def is_available(self) -> bool:
        """是否拿到了可信的识别文本。"""
        return not self.unavailable_reason


def detect_backend_kind(model_dir: Path) -> str:
    """根据模型目录中的 ``config.json`` / ``backend_meta.json`` 推断后端类型。

    优先读取写入的 ``backend_meta.json``；若不存在再扫描 HuggingFace 风格的
    ``config.json``。Qwen3-ASR 的 ``model_type`` 含 ``qwen``，Cohere Transcribe
    的目前为 ``cohere2_audio``，但只要包含 ``cohere`` 都视为 Cohere。
    """

    meta_path = model_dir / BACKEND_META_FILENAME
    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            kind = str(data.get("kind") or "").strip().lower()
            if kind in {BACKEND_KIND_QWEN, BACKEND_KIND_COHERE}:
                return kind
        except (OSError, json.JSONDecodeError):
            pass

    config_path = model_dir / "config.json"
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            config = {}
        signature = " ".join(
            str(value).lower()
            for value in (
                config.get("model_type"),
                config.get("architectures"),
                config.get("_name_or_path"),
            )
            if value
        )
        if "cohere" in signature:
            return BACKEND_KIND_COHERE
        if "qwen" in signature:
            return BACKEND_KIND_QWEN

    # 仓库名带 cohere 的目录默认视为 Cohere
    if "cohere" in model_dir.name.lower():
        return BACKEND_KIND_COHERE
    if "qwen" in model_dir.name.lower():
        return BACKEND_KIND_QWEN

    return BACKEND_KIND_UNKNOWN


class _AsrBackend:
    """ASR 后端基类：约定 ``load`` 与 ``transcribe`` 两个方法。"""

    kind: str = BACKEND_KIND_UNKNOWN
    required_modules: tuple[str, ...] = ()

    def __init__(self, model_path: Path):
        self.model_path = Path(model_path)
        self._loaded: Any | None = None

    def transcribe(
        self, audio_path: str | Path, language: str = "English", context: str = ""
    ) -> str:
        raise NotImplementedError


class _QwenAsrBackend(_AsrBackend):
    kind = BACKEND_KIND_QWEN
    required_modules = ("qwen_asr", "torch")

    def _load(self):
        if self._loaded is not None:
            return self._loaded

        try:
            import torch
            from qwen_asr import Qwen3ASRModel
        except ImportError as exc:
            raise AsrRuntimeError("未安装 qwen_asr 或 torch，无法运行 Qwen3-ASR") from exc

        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device.startswith("cuda") else torch.float32
        batch_size = 8 if device.startswith("cuda") else 1

        try:
            model = Qwen3ASRModel.from_pretrained(
                str(self.model_path),
                dtype=dtype,
                device_map=device,
                max_inference_batch_size=batch_size,
            )
        except Exception as exc:
            raise AsrRuntimeError(f"加载 Qwen3-ASR 模型失败: {str(exc)}") from exc

        self._loaded = model
        return model

    def transcribe(
        self, audio_path: str | Path, language: str = "English", context: str = ""
    ) -> str:
        """转写音频。

        Args:
            context: 热词/领域上下文提示串（system 词汇偏置），由服务层按
                全局热词配置组装；空串与 qwen_asr 默认一致，等价不注入。
        """
        model = self._load()
        try:
            results = model.transcribe(audio=str(audio_path), language=language, context=context)
        except Exception as exc:
            raise AsrRuntimeError(f"ASR 识别失败: {str(exc)}") from exc

        if not results:
            return ""

        result = results[0]
        if hasattr(result, "text"):
            return str(result.text or "").strip()
        if isinstance(result, dict):
            return str(result.get("text", "")).strip()
        return str(result or "").strip()


class _CohereTranscribeBackend(_AsrBackend):
    kind = BACKEND_KIND_COHERE
    required_modules = ("transformers", "torch", "librosa")

    def _load(self):
        if self._loaded is not None:
            return self._loaded

        try:
            import torch
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
        except ImportError as exc:
            raise AsrRuntimeError(
                "未安装 transformers 或 torch，无法运行 Cohere Transcribe"
            ) from exc

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32

        try:
            processor = AutoProcessor.from_pretrained(
                str(self.model_path), local_files_only=True, trust_remote_code=True
            )
            model = AutoModelForSpeechSeq2Seq.from_pretrained(
                str(self.model_path),
                local_files_only=True,
                trust_remote_code=True,
                torch_dtype=dtype,
            )
            model.to(device)
            model.eval()
        except Exception as exc:
            raise AsrRuntimeError(f"加载 Cohere Transcribe 模型失败: {str(exc)}") from exc

        self._loaded = (processor, model, device, dtype)
        return self._loaded

    @staticmethod
    def _read_audio_waveform(audio_path: str | Path) -> "np.ndarray":
        try:
            import scipy.signal
            from scipy.io import wavfile

            # 用 scipy 读取 WAV（避免 libsndfile 对 wave 模块写出的文件兼容性问题导致 C 级崩溃）
            sr, raw_data = wavfile.read(str(audio_path))
            waveform = raw_data.astype(np.float32)
            if np.issubdtype(raw_data.dtype, np.integer):
                waveform = waveform / np.iinfo(raw_data.dtype).max
            # 立体声转单声道
            if waveform.ndim > 1:
                waveform = waveform.mean(axis=1)
            # 重采样到目标采样率
            if sr != COHERE_TARGET_SAMPLE_RATE:
                waveform = scipy.signal.resample_poly(
                    waveform, COHERE_TARGET_SAMPLE_RATE, sr
                ).astype(np.float32)
            return waveform
        except ImportError:
            # fallback 到 librosa
            try:
                import librosa
                return librosa.load(str(audio_path), sr=COHERE_TARGET_SAMPLE_RATE, mono=True)[0]
            except ImportError as exc:
                raise AsrRuntimeError("未安装 scipy 或 librosa，无法读取音频") from exc
        except Exception as exc:
            raise AsrRuntimeError(f"读取录音文件失败: {str(exc)}") from exc

    @staticmethod
    def _normalize_language(language: str) -> str:
        normalized = str(language or "").strip().lower()
        return COHERE_LANGUAGE_ALIASES.get(normalized, normalized or "en")

    def transcribe(
        self, audio_path: str | Path, language: str = "English", context: str = ""
    ) -> str:
        # context 仅供 Qwen3-ASR 的 system 消息词汇偏置；Cohere 后端无此机制，
        # 接受参数但忽略（由实现保证，服务层无需按后端类型分支）。
        processor, model, device, dtype = self._load()
        waveform = self._read_audio_waveform(audio_path)
        normalized_language = self._normalize_language(language)

        try:
            import torch

            inputs = processor(
                audio=waveform,
                sampling_rate=COHERE_TARGET_SAMPLE_RATE,
                return_tensors="pt",
            )
            inputs = {key: value.to(device) for key, value in inputs.items()}
            if "input_features" in inputs and inputs["input_features"].dtype != dtype:
                inputs["input_features"] = inputs["input_features"].to(dtype)

            # max_new_tokens 降到64，TTS 输出通常不超过20个token
            generate_kwargs: dict[str, Any] = {"max_new_tokens": 64}
            try:
                forced_ids = processor.get_decoder_prompt_ids(language=normalized_language)
                if forced_ids:
                    generate_kwargs["forced_decoder_ids"] = forced_ids
            except (AttributeError, TypeError, ValueError):
                pass

            with torch.inference_mode():
                generated = model.generate(**inputs, **generate_kwargs)

            text = processor.batch_decode(generated, skip_special_tokens=True)
        except Exception as exc:
            raise AsrRuntimeError(f"Cohere Transcribe 识别失败: {str(exc)}") from exc

        if not text:
            return ""
        return str(text[0] or "").strip()


_BACKEND_REGISTRY: dict[str, type[_AsrBackend]] = {
    BACKEND_KIND_QWEN: _QwenAsrBackend,
    BACKEND_KIND_COHERE: _CohereTranscribeBackend,
}


def build_backend(kind: str, model_path: Path) -> _AsrBackend:
    backend_cls = _BACKEND_REGISTRY.get(kind)
    if backend_cls is None:
        raise AsrRuntimeError(
            f"无法识别模型目录 {model_path.name} 所属的后端类型，"
            "请确认导入的是 Qwen3-ASR 或 Cohere Transcribe 模型"
        )
    return backend_cls(model_path)


class Recorder:
    """Minimal audio recorder used by the ASR execution flow."""

    def __init__(self, sample_rate: int = 44100, channels: int = 1, device: int | None = None):
        self.sample_rate = sample_rate
        self.channels = channels
        self.actual_channels = channels  # 录制时实际使用的通道数
        self.device = device
        self.recording_data: list[np.ndarray] = []
        self.stream = None

    def start_recording(self) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise AsrRuntimeError("未安装 sounddevice，无法录音") from exc

        self.recording_data = []

        # 打印设备信息，优先使用 WASAPI host API
        is_loopback = False
        actual_channels = self.channels
        use_device = self.device
        extra_settings = None
        if self.device is not None:
            try:
                dev_info = sd.query_devices(self.device)
                hostapi_name = sd.query_hostapis()[dev_info["hostapi"]]["name"]
                max_in = dev_info["max_input_channels"]
                is_output = max_in == 0 and dev_info["max_output_channels"] > 0
                _log.info(
                    "[录音] 请求设备 #%d: %s | 输入通道=%d | 输出通道=%d | 采样率=%.0f | hostapi=%s",
                    self.device, dev_info["name"], max_in,
                    dev_info["max_output_channels"],
                    dev_info["default_samplerate"], hostapi_name,
                )

                if is_output:
                    is_loopback = True
                    extra_settings = sd.WasapiSettings(loopback=True)
                    _log.info("[录音] 输出设备，启用 WASAPI loopback")
                elif max_in > 0 and max_in != self.channels:
                    actual_channels = max_in
                    self.actual_channels = actual_channels
                    _log.info("[录音] 使用设备原生通道数: %d", actual_channels)

                # 如果当前 host API 不是 WASAPI，尝试找 WASAPI 版本的同一设备
                if "wasapi" not in hostapi_name.lower() and not is_loopback:
                    wasapi_idx = None
                    for ha in sd.query_hostapis():
                        if "wasapi" not in ha["name"].lower():
                            continue
                        for dev_idx in ha["devices"]:
                            wasapi_dev = sd.query_devices(dev_idx)
                            if wasapi_dev["name"] == dev_info["name"] and wasapi_dev["max_input_channels"] > 0:
                                wasapi_idx = dev_idx
                                break
                    if wasapi_idx is not None:
                        _log.info("[录音] 切换到 WASAPI 版本: 设备 #%d", wasapi_idx)
                        use_device = wasapi_idx
                        wasapi_info = sd.query_devices(wasapi_idx)
                        if wasapi_info["max_input_channels"] != self.channels:
                            actual_channels = wasapi_info["max_input_channels"]
                            self.actual_channels = actual_channels
                            _log.info("[录音] WASAPI 设备原生通道数: %d", actual_channels)
                        if wasapi_info["default_samplerate"] != self.sample_rate:
                            self.sample_rate = int(wasapi_info["default_samplerate"])
                            _log.info("[录音] WASAPI 设备采样率: %d", self.sample_rate)
                    else:
                        _log.info("[录音] 未找到 WASAPI 版本，使用当前 host API")

            except Exception as e:
                _log.warning("[录音] 查询设备失败: %s", e)

        def callback(indata, frames, time_info, status):
            if status:
                _log.warning("[录音] stream status: %s", status)
            # 回调运行在 PortAudio 实时线程里，任何异常都不能让它逃逸到 cffi，
            # 否则会出现 "Exception ignored from cffi callback" 且录音块丢失。
            try:
                self.recording_data.append(indata.copy())
            except Exception as exc:
                _log.error("[录音] 回调采集音频数据失败: %s", exc, exc_info=True)

        try:
            kwargs = dict(
                samplerate=self.sample_rate,
                channels=actual_channels,
                callback=callback,
                device=use_device,
            )
            if extra_settings is not None:
                kwargs["extra_settings"] = extra_settings
            self.stream = sd.InputStream(**kwargs)
            self.stream.start()
        except Exception as exc:
            raise AsrRuntimeError(f"启动录音失败: {str(exc)}") from exc

    def stop_recording(self) -> None:
        stream = self.stream
        self.stream = None
        if stream is None:
            return

        # stop()/close() 各自 try，避免一个失败就跳过另一个，导致 PortAudio
        # 流泄漏、回调线程持续运行、内存不断累积（曾表现为 cffi 回调 MemoryError）。
        for action in ("stop", "close"):
            try:
                getattr(stream, action)()
            except Exception as exc:
                _log.warning("[录音] stream.%s 失败: %s", action, exc)

    def save_recording(self, output_file: str | Path) -> Path:
        """把采集缓冲写成 16bit 单声道 WAV。

        设备（如 USB 音频接口）常常只提供多通道输入，``actual_channels`` 因此会
        大于 1；但各路内容一致，录成立体声没有信息增益——下游 enhance_audio、
        reduce_noise 与 ASR 输入全部按单声道处理。这里直接降混，后续链路少做一次
        无意义的重复计算，也不再进入立体声专属的处理分支。

        Args:
            output_file: 目标 WAV 路径，父目录不存在时自动创建。

        Returns:
            写入后的文件路径。

        Raises:
            AsrRuntimeError: 缓冲为空，即未采集到任何音频数据。
        """
        if not self.recording_data:
            raise AsrRuntimeError("录音结果为空，未采集到音频数据")

        recording = np.concatenate(self.recording_data, axis=0)
        if recording.ndim > 1 and recording.shape[1] > 1:
            recording = recording.mean(axis=1)

        duration = len(recording) / self.sample_rate
        max_amp = float(np.max(np.abs(recording)))
        _log.info(
            "[录音] 保存: 时长=%.2fs, 最大振幅=%.6f, 数据块=%d, 设备=%s",
            duration, max_amp, len(self.recording_data), self.device
        )

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes((recording * 32767).astype(np.int16).tobytes())

        return output_path


class TextComparer:
    """Text similarity helper reused by the backend ASR flow."""

    _substitutions_cache: dict[str, str] | None = None
    _substitutions_mtime: float = 0.0

    @classmethod
    def _get_substitutions_path(cls) -> Path:
        return settings.WORKING_DIR / "asr_text_substitutions.json"

    @classmethod
    def load_substitutions(cls, force: bool = False) -> dict[str, str]:
        """从 JSON 文件加载替换规则（带 mtime 缓存）。"""
        path = cls._get_substitutions_path()
        if not path.exists():
            cls._substitutions_cache = {}
            cls._substitutions_mtime = 0.0
            return {}
        try:
            mtime = path.stat().st_mtime
            if not force and cls._substitutions_cache is not None and cls._substitutions_mtime == mtime:
                return cls._substitutions_cache
            data = json.loads(path.read_text(encoding="utf-8"))
            rules = {str(k).lower(): str(v) for k, v in data.items() if isinstance(data, dict)}
            cls._substitutions_cache = rules
            cls._substitutions_mtime = mtime
            return rules
        except (OSError, json.JSONDecodeError):
            cls._substitutions_cache = {}
            return {}

    @classmethod
    def save_substitutions(cls, rules: dict[str, str]) -> None:
        """保存替换规则到 JSON 文件。"""
        path = cls._get_substitutions_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        normalized = {str(k).lower(): str(v) for k, v in rules.items()}
        path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
        cls._substitutions_cache = normalized
        cls._substitutions_mtime = path.stat().st_mtime

    @classmethod
    def get_substitutions(cls) -> dict[str, str]:
        """获取当前替换规则。"""
        if cls._substitutions_cache is None:
            return cls.load_substitutions()
        return cls._substitutions_cache

    @classmethod
    def apply_substitutions(cls, text: str) -> str:
        """按规则依次替换文本（不区分大小写匹配）。"""
        rules = cls.get_substitutions()
        if not rules:
            return text
        for pattern, replacement in rules.items():
            text = re.sub(re.escape(pattern), replacement, text, flags=re.IGNORECASE)
        return text

    _NUMBER_WORDS = {
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
        "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
        "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
        "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
        "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
        "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
        "eighty": 80, "ninety": 90,
        "first": 1, "second": 2, "third": 3, "fourth": 4,
        "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
        "ninth": 9, "tenth": 10,
    }

    @staticmethod
    def clean_text(text: str) -> str:
        text = str(text or "").lower()
        # 应用用户自定义替换规则（在标点移除和数字转换之前）。
        # 替换值直接插入会破坏开头 lowercase 的大小写约定（如规则值 "HOME"），
        # 需再次小写，否则与全小写的参考文本比对必得 0 分。
        text = TextComparer.apply_substitutions(text).lower()
        # 将 "+" 和单词中的 "plus" 统一为分词 "plus"，确保 "Whale+" 和 "WhalePlus" 视为相同
        text = re.sub(r"\+", " plus ", text)
        text = re.sub(r"(\w)(plus)", r"\1 plus ", text)
        # 连字符 / 斜杠在语音里等同空格，必须先转成空格再走标点清理：否则
        # "Wi-Fi" 被删成 "wifi"，而参考列的 "Wi Fi" 是 "wi fi"，只差一个空格
        # 就要扣掉 4.19%（实测 95.81%）。撇号等仍按原样删除，保住
        # "don't" 与 "dont" 的匹配。
        text = re.sub(r"[-/–—]", " ", text)
        text = re.sub(r"[^\w\s]", "", text)
        # 将英文数字单词转为阿拉伯数字（volume four → volume 4, fifty three → 53）
        words = text.split()
        result = []
        pending_tens = None
        for w in words:
            val = TextComparer._NUMBER_WORDS.get(w)
            if val is None:
                if pending_tens is not None:
                    result.append(str(pending_tens))
                    pending_tens = None
                result.append(w)
            elif val >= 20 and val % 10 == 0:
                # 十位数（twenty, thirty, ...），先暂存
                if pending_tens is not None:
                    result.append(str(pending_tens))
                pending_tens = val
            else:
                if pending_tens is not None:
                    # 组合：fifty three → 53
                    result.append(str(pending_tens + val))
                    pending_tens = None
                else:
                    result.append(str(val))
        if pending_tens is not None:
            result.append(str(pending_tens))
        return " ".join(result)

    @classmethod
    def cosine_similarity(cls, text1: str, text2: str) -> float:
        normalized1 = cls.clean_text(text1)
        normalized2 = cls.clean_text(text2)
        if not normalized1 or not normalized2:
            return 0.0

        vector1 = Counter(normalized1)
        vector2 = Counter(normalized2)
        tokens = set(vector1.keys()) | set(vector2.keys())
        dot_product = sum(vector1.get(token, 0) * vector2.get(token, 0) for token in tokens)
        magnitude1 = math.sqrt(sum(vector1.get(token, 0) ** 2 for token in tokens))
        magnitude2 = math.sqrt(sum(vector2.get(token, 0) ** 2 for token in tokens))
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        return dot_product / (magnitude1 * magnitude2)

    @classmethod
    def sequence_similarity(cls, text1: str, text2: str) -> float:
        normalized1 = cls.clean_text(text1)
        normalized2 = cls.clean_text(text2)
        if not normalized1 or not normalized2:
            return 0.0
        return SequenceMatcher(None, normalized1, normalized2).ratio()

    @classmethod
    def compare(cls, text1: str, text2: str, threshold: float = 0.9) -> dict[str, Any]:
        cosine = cls.cosine_similarity(text1, text2)
        sequence = cls.sequence_similarity(text1, text2)
        average = (cosine + sequence) / 2
        return {
            "cosine": cosine,
            "sequence": sequence,
            "average": average,
            "threshold": threshold,
            "matched": average >= threshold,
            "result": "PASS" if average >= threshold else "FAIL",
        }


def _normalize_for_match(text: str) -> str:
    """归一化文本用于热词比对：小写、非字母数字转空格、折叠空白。"""
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _split_segments(text: str) -> list[str]:
    """按中英文标点把识别文本切段，供复读判定使用。"""
    return [part for part in re.split(r"[,.;:!?，。；：！？]", text) if part.strip()]


def _prompt_words(prompt: str) -> set[str]:
    """从提示串还原本次注入的词表（``build_context_prompt`` 的逆操作）。

    Args:
        prompt: 形如 "Vocabulary: word1, word2" 的提示串。

    Returns:
        归一化后的词集合；词条内部空格原样保留（"app setting" 视为一个词）。
    """
    body = prompt[len(CONTEXT_PROMPT_PREFIX):] if prompt.startswith(CONTEXT_PROMPT_PREFIX) else prompt
    return {
        word
        for word in (_normalize_for_match(part) for part in body.split(","))
        if word
    }


def _is_prompt_echo(transcript: str, prompt: str) -> bool:
    """判断识别结果是否只是把注入的热词提示串复读了回来。

    Qwen3-ASR 面对静音/噪声时会顺势续写 context、直接吐回整张词表
    （实测：4.6s 静音录音 → "Vocabulary: app setting, HOME, ..."）。
    这种输出没有任何识别价值，当成真实文本参与比对会产出看似合理的分数，
    必须在服务层丢弃。

    判定要求「词表不少于 N 条」且「识别结果切段后每段都是词表里的词」，
    两个条件同时成立才丢弃：正常语音里夹带几个热词（如 "the apps menu shows
    HOME"）因含非热词段而不会误判。

    Args:
        transcript: 模型识别文本。
        prompt: 本次实际注入的提示串；为空表示未注入词表，不可能复读。

    Returns:
        识别结果等价于提示串词表时为 True。
    """
    if not transcript or not prompt:
        return False

    words = _prompt_words(prompt)
    if len(words) < PROMPT_ECHO_MIN_SEGMENTS:
        return False

    prefix = _normalize_for_match(CONTEXT_PROMPT_PREFIX)
    segments = [
        normalized
        for normalized in (_normalize_for_match(part) for part in _split_segments(transcript))
        if normalized and normalized != prefix
    ]
    if len(segments) < PROMPT_ECHO_MIN_SEGMENTS:
        return False
    return all(segment in words for segment in segments)


class AsrContextWords:
    """Qwen3-ASR 全局热词词表：读纯文本文件，组装 context 提示串。

    热词经 system context 注入做解码偏置，只对 Qwen3-ASR 后端生效（Cohere
    Transcribe 无此机制，参数接受并忽略）。词表文件每行一个词/短语，# 开头
    为注释行；文件缺失或词表为空 = 不注入（A/B 基线）。热路径每次识别 stat
    一次文件 mtime，外部手改保存后下一次识别即生效，无需重启后端；不做文件
    锁，半写窗口最多读到残缺词表（只影响当次识别），下次自愈。
    """

    _words_cache: list[str] | None = None
    _words_mtime: float = 0.0

    @classmethod
    def _get_words_path(cls) -> Path:
        return settings.WORKING_DIR / ASR_HOTWORDS_FILENAME

    @classmethod
    def _clean_lines(cls, lines: list[str]) -> list[str]:
        """清洗词表行：去空、跳过 # 注释、保序去重、截断超限词条与总数。

        词条只做 strip 不做内部空白折叠——"app setting" 这类英文短语必须
        原样保留才能作为整体热词。
        """
        words: list[str] = []
        for raw_line in lines:
            word = raw_line.strip()
            if not word or word.startswith("#") or word in words:
                continue
            words.append(word[:MAX_CONTEXT_WORD_CHARS])
            if len(words) >= MAX_CONTEXT_WORDS:
                break
        return words

    @classmethod
    def _read_words_file(cls) -> list[str]:
        """读词表文件；文件缺失或读取失败视为空词表（= 基线），不抛异常。"""
        try:
            lines = cls._get_words_path().read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        return cls._clean_lines(lines)

    @classmethod
    def get_words(cls) -> list[str]:
        """获取规范化词表（每次调用 stat 一次 mtime，感知外部手改）。

        Returns:
            词表副本；文件缺失/被删时返回空列表（不注入，等同基线）。
        """
        path = cls._get_words_path()
        try:
            mtime = path.stat().st_mtime
        except OSError:
            cls._words_cache = []
            cls._words_mtime = 0.0
            return []
        if cls._words_cache is not None and cls._words_mtime == mtime:
            return list(cls._words_cache)
        words = cls._read_words_file()
        cls._words_cache = words
        cls._words_mtime = mtime
        return list(words)

    @classmethod
    def build_context_prompt(cls) -> str:
        """组装 context 热词提示串。

        Returns:
            形如 "Vocabulary: word1, word2" 的提示串；词表为空时返回空串
            （等价不注入，保证与旧行为逐字节一致）。
        """
        words = cls.get_words()
        if not words:
            return ""
        return f"{CONTEXT_PROMPT_PREFIX}{', '.join(words)}"


def _to_mono_float(raw_data: np.ndarray) -> np.ndarray:
    """整数 WAV 样本归一化到 [-1, 1] 并降混为单声道。

    Args:
        raw_data: ``scipy.io.wavfile.read`` 返回的原始样本数组。

    Returns:
        单声道 float64 数组。
    """
    data = raw_data.astype(np.float64)
    if np.issubdtype(raw_data.dtype, np.integer):
        data = data / np.iinfo(raw_data.dtype).max
    return data.mean(axis=1) if data.ndim > 1 else data


def _read_wav_mono(audio_path: str | Path) -> np.ndarray:
    """读 WAV 为单声道 float64 数组，幅度归一到 [-1, 1]。

    用 scipy 而非 libsndfile：录音由 stdlib ``wave`` 写出，libsndfile 读它存在
    C 级崩溃风险（与 ``reduce_noise`` 同因，见那里的注释）。

    Args:
        audio_path: WAV 文件路径。

    Returns:
        单声道采样数组。
    """
    from scipy.io import wavfile

    return _to_mono_float(wavfile.read(str(audio_path))[1])


def _measure_noise_floor_dbfs(data: np.ndarray, sample_rate: int) -> float | None:
    """估计录音的本底噪声（dBFS）。

    取分帧 RMS 的低分位数：语音只占整段录音的一小部分，最安静的那批帧反映的
    就是本底，不受说话人音量影响。

    Args:
        data: 单声道采样数组，幅度已归一到 [-1, 1]。
        sample_rate: 采样率。

    Returns:
        本底噪声（dBFS）；录音短到无法分帧时返回 None（无从判断）。
    """
    frame_length = max(1, int(sample_rate * NOISE_FLOOR_FRAME_SECONDS))
    frame_count = len(data) // frame_length
    if frame_count < 1:
        return None
    frames = data[: frame_count * frame_length].reshape(frame_count, frame_length)
    frame_rms = np.sqrt(np.mean(frames ** 2, axis=1))
    quietest_frame = float(np.percentile(frame_rms, NOISE_FLOOR_PERCENTILE))
    return 20 * np.log10(max(quietest_frame, 1e-10))


def _should_reduce_noise(noise_floor_dbfs: float | None) -> bool:
    """判断录音是否真有噪声可降。

    Args:
        noise_floor_dbfs: ``_measure_noise_floor_dbfs`` 的返回值。

    Returns:
        是否需要降噪。噪声底无从判断（None）时返回 False：降噪实测会拉低
        识别率，判断不了就不做。
    """
    if noise_floor_dbfs is None:
        return False
    return noise_floor_dbfs > NOISE_FLOOR_SKIP_DBFS


def _is_silent_audio(audio_path: str | Path) -> bool:
    """判断录音是否为静音（无语音能量）。

    读文件失败时返回 False（放行识别）：判定失败不应反过来阻断正常流程，
    对静音录音的兜底还有 ``_is_prompt_echo`` 一道。

    Args:
        audio_path: WAV 文件路径。

    Returns:
        RMS 低于 ``SILENT_AUDIO_RMS_FLOOR`` 时为 True。
    """
    try:
        data = _read_wav_mono(audio_path)
    except (OSError, ValueError) as exc:
        _log.warning("[ASR] 读取音频算能量失败，跳过静音判定: %s | %s", audio_path, exc)
        return False
    if data.size == 0:
        return True
    return float(np.sqrt(np.mean(np.square(data)))) < SILENT_AUDIO_RMS_FLOOR


class AsrService:
    """提供 ASR 资源探测、运行时模型管理和执行依赖信息。"""

    def __init__(self):
        self.project_root = settings.WORKING_DIR / "Project"
        self.bundle_project_root = settings.BUNDLE_DIR / "Project"
        self.voice_project_root = self.project_root / "voice_recorder_compare"
        self.bundle_voice_project_root = self.bundle_project_root / "voice_recorder_compare"
        self.qwen_root = self._resolve_existing_dir(self.project_root / "Qwen", self.bundle_project_root / "Qwen")
        self.runtime_model_root = settings.ASR_MODELS_DIR
        self.runtime_state_file = settings.WORKING_DIR / "asr_runtime_state.json"
        self.case_root = self._resolve_existing_dir(self.voice_project_root / "case", self.bundle_voice_project_root / "case")
        self.reference_root = self._resolve_existing_dir(self.voice_project_root / "references", self.bundle_voice_project_root / "references")
        self.audio_root = self.voice_project_root / "audio"
        self.result_root = self.voice_project_root / "results"
        self.log_root = self.voice_project_root / "logs"
        self._loaded_backend: _AsrBackend | None = None
        self._loaded_model_name = ""
        self._model_lock = Lock()

    @staticmethod
    def _resolve_existing_dir(runtime_dir: Path, bundle_dir: Path) -> Path:
        if runtime_dir.exists():
            return runtime_dir
        if bundle_dir.exists():
            return bundle_dir
        return runtime_dir

    def _list_files(self, folder: Path, patterns: tuple[str, ...]) -> list[str]:
        if not folder.exists() or not folder.is_dir():
            return []

        names: set[str] = set()
        for pattern in patterns:
            for item in folder.glob(pattern):
                if item.is_file():
                    names.add(item.name)
        return sorted(names)

    def _read_runtime_state(self) -> dict[str, Any]:
        if not self.runtime_state_file.exists():
            return {}

        try:
            return json.loads(self.runtime_state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_runtime_state(self, data: dict[str, Any]) -> None:
        self.runtime_state_file.parent.mkdir(parents=True, exist_ok=True)
        self.runtime_state_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_audio_config(self) -> dict[str, Any]:
        state = self._read_runtime_state()
        return {
            "audio_input_mode": state.get("audio_input_mode", "speaker"),
            "audio_device_index": state.get("audio_device_index"),
        }

    def set_audio_config(self, audio_input_mode: str, audio_device_index: int | None = None) -> dict[str, Any]:
        if audio_input_mode not in ("speaker", "capture_card"):
            raise ValueError(f"无效的录制模式: {audio_input_mode}")
        state = self._read_runtime_state()
        state["audio_input_mode"] = audio_input_mode
        state["audio_device_index"] = audio_device_index
        self._write_runtime_state(state)
        return {"audio_input_mode": audio_input_mode, "audio_device_index": audio_device_index}

    @staticmethod
    def list_audio_devices() -> list[dict[str, Any]]:
        import sounddevice as sd
        devices = sd.query_devices()
        default_input = sd.default.device[0]
        default_output = sd.default.device[1]
        hostapis = sd.query_hostapis()

        result = []
        for i, d in enumerate(devices):
            is_input = d["max_input_channels"] > 0
            is_output = d["max_output_channels"] > 0
            if not is_input and not is_output:
                continue

            ha_name = hostapis[d["hostapi"]]["name"] if d["hostapi"] < len(hostapis) else "unknown"
            device_type = "input" if is_input else "output"
            result.append({
                "index": i,
                "name": d["name"],
                "type": device_type,
                "hostapi": ha_name,
                "input_channels": d["max_input_channels"],
                "output_channels": d["max_output_channels"],
                "sample_rate": d["default_samplerate"],
                "is_default": (i == default_input) if is_input else (i == default_output),
            })
        return result

    def _sanitize_model_name(self, model_name: str) -> str:
        normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", str(model_name or "").strip())
        normalized = normalized.strip("._")
        if not normalized:
            raise ValueError("模型名称不能为空")
        return normalized

    def _sanitize_relative_path(self, relative_path: str) -> Path:
        sanitized = Path(str(relative_path or "").replace("\\", "/").strip("/"))
        if sanitized.is_absolute() or any(part == ".." for part in sanitized.parts):
            raise ValueError("模型文件路径不合法")
        if not sanitized.parts:
            raise ValueError("模型文件路径不能为空")
        return sanitized

    def _sanitize_case_name(self, value: str) -> str:
        normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
        return normalized.strip("._") or "case"

    def _normalize_reference_key(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())

    def _inspect_dependency(self, module_name: str) -> dict[str, Any]:
        try:
            module_spec = importlib.util.find_spec(module_name)
        except (ImportError, ValueError) as exc:
            return {
                "available": False,
                "missing_module": module_name,
                "error": f"检查模块 {module_name} 失败: {exc.__class__.__name__}: {str(exc)}",
            }

        if module_spec is None:
            return {
                "available": False,
                "missing_module": module_name,
                "error": f"未找到模块 {module_name}",
            }

        try:
            importlib.import_module(module_name)
        except ImportError as exc:
            missing_module = getattr(exc, "name", "") or module_name
            if missing_module == module_name:
                error_text = f"导入 {module_name} 失败: {str(exc)}"
            else:
                error_text = f"导入 {module_name} 失败，当前缺少其传递依赖 {missing_module}: {str(exc)}"
            return {
                "available": False,
                "missing_module": missing_module,
                "error": error_text,
            }
        except Exception as exc:
            return {
                "available": False,
                "missing_module": None,
                "error": f"导入 {module_name} 失败: {exc.__class__.__name__}: {str(exc)}",
            }

        return {
            "available": True,
            "missing_module": None,
            "error": "",
        }

    def _dependency_available(self, module_name: str) -> bool:
        return self._inspect_dependency(module_name)["available"]

    def get_runtime_dependency_status(self) -> dict[str, Any]:
        dependency_details = {
            "sounddevice": self._inspect_dependency("sounddevice"),
            "qwen_asr": self._inspect_dependency("qwen_asr"),
            "torch": self._inspect_dependency("torch"),
            "transformers": self._inspect_dependency("transformers"),
            "librosa": self._inspect_dependency("librosa"),
            "huggingface_hub": self._inspect_dependency("huggingface_hub"),
        }
        available = {
            name: bool(details["available"])
            for name, details in dependency_details.items()
        }

        # ``sounddevice`` / ``torch`` 是录音与推理的硬依赖；其余按当前激活模型的
        # 后端类型决定是否必需，以避免"用 Qwen 时却抱怨 transformers 缺失"。
        active_model = self.get_active_model()
        active_kind = (active_model or {}).get("kind", BACKEND_KIND_UNKNOWN)
        required_modules: set[str] = {"sounddevice", "torch"}
        if active_kind == BACKEND_KIND_COHERE:
            required_modules.update({"transformers", "librosa"})
        elif active_kind == BACKEND_KIND_QWEN:
            required_modules.add("qwen_asr")
        else:
            # 未选择模型时，至少保证基础录音依赖；其它依赖在用户选模型后再校验。
            pass

        missing = sorted(name for name in required_modules if not available.get(name, False))
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        is_frozen_runtime = bool(getattr(sys, "frozen", False))
        install_commands = []
        if "qwen_asr" in missing:
            install_commands.append("python -m pip install -U qwen-asr")
        if "transformers" in missing:
            install_commands.append("python -m pip install -U transformers")
        if "librosa" in missing:
            install_commands.append("python -m pip install -U librosa soundfile")
        if "sounddevice" in missing:
            install_commands.append("python -m pip install -U sounddevice")
        if "torch" in missing:
            install_commands.append("python -m pip install torch --index-url https://download.pytorch.org/whl/cpu")

        if missing and is_frozen_runtime:
            install_steps = [
                "当前运行的是打包版 AutoDeck.exe，不能通过给 exe 外部执行 pip install 直接补进已打包依赖。",
                "请在用于执行 build_exe.bat 的 Python 环境中，先执行 python -m pip install -U pip。",
            ]
            install_steps.extend([f"在打包环境执行: {command}" for command in install_commands])
            install_steps.append("重新运行 build_exe.bat 生成新的 AutoDeck.exe，并替换当前 dist 目录中的程序。")
            install_steps.append("重启新的 AutoDeck.exe 后，再回到当前页面点击“刷新状态”。")
        else:
            install_steps = [
                "建议使用独立的 Python 3.12 虚拟环境安装 ASR 依赖，避免与当前项目环境冲突。",
                "进入该环境后，先执行 python -m pip install -U pip。",
            ]
            install_steps.extend([f"执行: {command}" for command in install_commands])
            install_steps.append("安装完成后重启后端服务，再回到当前页面点击“刷新状态”。")

        notes = []
        for module_name, details in dependency_details.items():
            if details["available"]:
                continue
            error_text = str(details.get("error") or "").strip()
            if not error_text:
                continue
            if details.get("missing_module") not in {None, "", module_name}:
                notes.append(error_text)
                continue
            if error_text.startswith("导入"):
                notes.append(error_text)
        if is_frozen_runtime:
            notes.append(f"当前后端运行在打包版进程中: {sys.executable}")
        if sys.version_info >= (3, 14):
            notes.append(
                f"当前后端运行在 Python {python_version}。qwen-asr 官方更推荐使用新的 Python 3.12 环境。"
            )

        return {
            "available": available,
            "dependency_details": dependency_details,
            "ready": not missing,
            "missing": missing,
            "python_version": python_version,
            "runtime_mode": "frozen" if is_frozen_runtime else "source",
            "executable_path": sys.executable,
            "recommended_python_version": "3.12",
            "install_commands": install_commands,
            "install_steps": install_steps,
            "notes": notes,
            "restart_required": bool(missing),
        }

    def create_recorder(self, device: int | None = None) -> Recorder:
        return Recorder(device=device)

    def _load_runtime_model(self) -> _AsrBackend:
        active_model = self.get_active_model()
        if active_model is None:
            raise AsrRuntimeError("请先导入并选择 ASR 模型")

        model_name = active_model["name"]
        model_path = Path(active_model["path"])
        kind = active_model.get("kind", BACKEND_KIND_UNKNOWN)

        with self._model_lock:
            if self._loaded_backend is not None and self._loaded_model_name == model_name:
                return self._loaded_backend

            backend = build_backend(kind, model_path)
            self._loaded_backend = backend
            self._loaded_model_name = model_name
            return backend

    def transcribe_audio(
        self, audio_path: str | Path, language: str = "English", context: str | None = None
    ) -> TranscriptionResult:
        """ASR 识别。

        静音录音直接跳过推理——既不浪费一次计算，也避免模型对着静音续写注入的
        context（实测会吐回整张热词表）；识别结果若被判定为复读提示串同样丢弃。

        Args:
            context: 显式 context 提示串；传 None 时自动套用全局热词词表
                （AsrContextWords），词表为空则注入空串（与旧行为一致，
                即 A/B 基线）；显式传值（含 ""）可覆盖/临时关闭词表注入。

        Returns:
            识别结果；不可信时 ``is_available`` 为 False 且 ``unavailable_reason``
            说明原因。
        """
        if context is None:
            context = AsrContextWords.build_context_prompt()
        if _is_silent_audio(audio_path):
            _log.warning("[ASR] 录音能量过低，判定为静音并跳过识别: %s", audio_path)
            return TranscriptionResult(unavailable_reason=TRANSCRIPT_SILENT_REASON)

        backend = self._load_runtime_model()
        transcript = backend.transcribe(audio_path, language=language, context=context)
        if _is_prompt_echo(transcript, context):
            _log.warning("[ASR] 识别结果复读了热词提示串，已丢弃: %s", transcript)
            return TranscriptionResult(unavailable_reason=TRANSCRIPT_ECHO_REASON)
        return TranscriptionResult(text=transcript)

    def save_audio_recording(self, recorder: Recorder, case_title: str) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_path = self.audio_root / f"recording_{self._sanitize_case_name(case_title)}_{timestamp}.wav"
        return recorder.save_recording(target_path)

    @staticmethod
    def _compute_normalization_gain(reference: np.ndarray, target_db: float) -> float:
        """按参考信号的 RMS 估算归一化增益。

        返回**标量**：多通道必须共用同一个增益，否则通道间的相对电平被破坏，
        立体声平衡随之丢失。

        Args:
            reference: 用于估算现有电平的参考信号（多通道时传通道均值）。
            target_db: 目标音量（dB）。

        Returns:
            增益倍数；参考信号近似静音时返回 1.0（不做归一化）。
        """
        current_rms = float(np.sqrt(np.mean(reference ** 2)))
        if current_rms <= 1e-6:  # 避免除以零
            return 1.0

        target_rms = 10 ** (target_db / 20)
        gain = min(max(target_rms / current_rms, NORMALIZATION_GAIN_MIN), NORMALIZATION_GAIN_MAX)
        _log.info(
            "[增强] 音量归一化: 增益=%.2f (原始 RMS=%.4f, 目标 RMS=%.4f)",
            gain, current_rms, target_rms,
        )
        return gain

    @staticmethod
    def _add_voice_band(data: np.ndarray, sample_rate: int) -> np.ndarray:
        """叠加 300Hz-3kHz 带通分量，增强人声清晰度。

        滤波沿时间轴（``axis=0``）作用，多通道共用同一组系数，通道间的幅度与
        相位关系保持不变。

        Args:
            data: 已归一到 [-1, 1] 的波形，形状为 (样本数,) 或 (样本数, 通道数)。
            sample_rate: 采样率。

        Returns:
            叠加人声频段后的波形；频段越界（采样率过低）时原样返回。
        """
        from scipy.signal import butter, filtfilt

        nyquist = sample_rate / 2
        low_freq = VOICE_BAND_LOW_HZ / nyquist
        high_freq = min(VOICE_BAND_HIGH_HZ / nyquist, 0.95)  # 不超过奈奎斯特频率
        if low_freq >= high_freq:
            return data

        b, a = butter(4, [low_freq, high_freq], btype="band")
        _log.info(
            "[增强] 人声频段增强: %dHz-%dHz, 增益=%.1f",
            VOICE_BAND_LOW_HZ, VOICE_BAND_HIGH_HZ, VOICE_BAND_BOOST,
        )
        return data + VOICE_BAND_BOOST * filtfilt(b, a, data, axis=0)

    @staticmethod
    def enhance_audio(audio_path: str | Path, target_db: float = -20.0, voice_boost: bool = True) -> Path:
        """音频增强：音量归一化 + 人声频段增强，原地替换。

        增益与带通滤波都是线性运算，直接作用在整个多通道数组上——每个通道因此
        拿到完全相同的增益和滤波器，立体声平衡天然保持，无需任何逐通道补偿。

        Args:
            audio_path: WAV 文件路径
            target_db: 目标音量（dB），默认 -20 dB
            voice_boost: 是否增强人声频段（300Hz-3kHz），默认 True
        """
        from scipy.io import wavfile

        audio_path = Path(audio_path)
        sr, raw_data = wavfile.read(str(audio_path))
        data = raw_data.astype(np.float64)

        # 归一化到 [-1, 1]
        max_val = 1.0
        if np.issubdtype(raw_data.dtype, np.integer):
            max_val = float(np.iinfo(raw_data.dtype).max)
            data = data / max_val

        reference = data.mean(axis=1) if data.ndim > 1 else data
        data = data * AsrService._compute_normalization_gain(reference, target_db)

        if voice_boost and sr > VOICE_BOOST_MIN_SAMPLE_RATE:  # 采样率太低时跳过
            data = AsrService._add_voice_band(data, sr)

        data = np.clip(data, -1.0, 1.0)  # 防止削波

        # 转换回原始数据类型并写入
        if np.issubdtype(raw_data.dtype, np.integer):
            data = (data * max_val).astype(raw_data.dtype)
        else:
            data = data.astype(raw_data.dtype)

        wavfile.write(str(audio_path), sr, data)
        _log.info("[增强] 完成: %s (采样率=%d, 时长=%.2fs)", audio_path.name, sr, len(data) / sr)
        return audio_path

    @staticmethod
    def boost_volume(audio_path: str | Path, factor: float = 2.0) -> Path:
        """对 WAV 文件做音量增益放大，原地替换。

        Args:
            audio_path: WAV 文件路径
            factor: 放大倍数，默认 2.0（即增加 100%，音量翻倍）
        """
        from scipy.io import wavfile

        audio_path = Path(audio_path)
        sr, raw_data = wavfile.read(str(audio_path))
        data = raw_data.astype(np.float64)
        original_dtype = raw_data.dtype

        # 归一化到 [-1, 1]
        if np.issubdtype(original_dtype, np.integer):
            max_val = np.iinfo(original_dtype).max
            data = data / max_val

        # 增益放大
        data = data * factor

        # 防止削波
        data = np.clip(data, -1.0, 1.0)

        # 转换回原始数据类型并写入
        if np.issubdtype(original_dtype, np.integer):
            data = (data * max_val).astype(original_dtype)
        else:
            data = data.astype(original_dtype)

        wavfile.write(str(audio_path), sr, data)
        _log.info("[音量增强] 完成: %s (倍率=%.2f, 采样率=%d)", audio_path.name, factor, sr)
        return audio_path

    @staticmethod
    def reduce_noise(audio_path: str | Path) -> Path:
        """对 WAV 文件做离线降噪（频谱门控），原地替换。

        先量本底噪声，只有确实存在噪声时才降：采集卡数字直采的录音底噪已贴到
        16bit 量化极限，此时没有任何噪声可降，非平稳门控只会逐帧追着量化噪声
        开合，既制造伪影又拉低识别率（见 ``NOISE_FLOOR_SKIP_DBFS``）。
        noisereduce 未安装时同样跳过。

        Args:
            audio_path: WAV 文件路径。

        Returns:
            处理后的文件路径（跳过时原样返回）。
        """
        try:
            import noisereduce as nr
        except ImportError:
            _log.warning("[降噪] noisereduce 未安装，跳过降噪: pip install noisereduce")
            return Path(audio_path)

        import soundfile as sf
        from scipy.io import wavfile

        audio_path = Path(audio_path)
        # 用 scipy 读取 WAV（避免 libsndfile 对 wave 模块写出的文件兼容性问题导致 C 级崩溃）
        sr, raw_data = wavfile.read(str(audio_path))
        data = _to_mono_float(raw_data)

        noise_floor = _measure_noise_floor_dbfs(data, sr)
        if noise_floor is None:
            _log.info("[降噪] 跳过: %s (录音过短，本底噪声无从判断)", audio_path.name)
            return audio_path
        if not _should_reduce_noise(noise_floor):
            _log.info(
                "[降噪] 跳过: %s (本底噪声 %.1f dBFS 已贴量化极限，无噪声可降)",
                audio_path.name, noise_floor,
            )
            return audio_path

        reduced = nr.reduce_noise(y=data, sr=sr, stationary=False)
        sf.write(str(audio_path), reduced, sr)
        _log.info(
            "[降噪] 完成: %s (本底=%.1fdBFS, 采样率=%d, 时长=%.2fs)",
            audio_path.name, noise_floor, sr, len(reduced) / sr,
        )
        return audio_path

    def save_transcript(self, audio_path: str | Path, transcript: str) -> Path:
        audio_stem = Path(audio_path).stem
        target_path = self.result_root / f"transcript_{audio_stem}.txt"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(transcript or "", encoding="utf-8")
        return target_path

    def save_compare_report(
        self,
        audio_path: str | Path,
        transcript: str,
        reference_text: str,
        comparison: dict[str, Any],
    ) -> Path:
        audio_stem = Path(audio_path).stem
        target_path = self.result_root / f"compare_{audio_stem}.txt"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "=" * 70,
            "文本相似度对比结果",
            "=" * 70,
            "",
            f"余弦相似度:    {comparison['cosine'] * 100:.2f}%",
            f"序列相似度:    {comparison['sequence'] * 100:.2f}%",
            f"平均相似度:    {comparison['average'] * 100:.2f}%",
            f"判定结果:      {comparison['result']}",
            "",
            "-" * 70,
            "识别文本:",
            transcript or "",
            "",
            "参考文本:",
            reference_text or "",
        ]
        target_path.write_text("\n".join(lines), encoding="utf-8")
        return target_path

    def find_reference(self, case_title: str) -> dict[str, str] | None:
        if not self.reference_root.exists() or not self.reference_root.is_dir():
            return None

        reference_files = [item for item in self.reference_root.glob("*.txt") if item.is_file()]
        if not reference_files:
            return None

        target_key = self._normalize_reference_key(case_title)
        for reference_file in reference_files:
            if self._normalize_reference_key(reference_file.stem) == target_key:
                return {
                    "path": str(reference_file),
                    "text": reference_file.read_text(encoding="utf-8").strip(),
                }

        return None

    def compare_transcript(self, transcript: str, reference_text: str, threshold: float = 0.9) -> dict[str, Any]:
        return TextComparer.compare(transcript, reference_text, threshold=threshold)

    def _read_backend_meta(self, model_dir: Path) -> dict[str, Any]:
        meta_path = model_dir / BACKEND_META_FILENAME
        if not meta_path.exists():
            return {}
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write_backend_meta(self, model_dir: Path, kind: str, repo_id: str = "") -> None:
        meta_path = model_dir / BACKEND_META_FILENAME
        try:
            meta_path.write_text(
                json.dumps({"kind": kind, "repo_id": repo_id}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _ensure_backend_meta(self, model_dir: Path) -> str:
        """读取或推断模型目录的后端类型，并落到 ``backend_meta.json``。"""
        meta = self._read_backend_meta(model_dir)
        kind = str(meta.get("kind") or "").strip().lower()
        if kind in {BACKEND_KIND_QWEN, BACKEND_KIND_COHERE}:
            return kind

        kind = detect_backend_kind(model_dir)
        if kind in {BACKEND_KIND_QWEN, BACKEND_KIND_COHERE}:
            self._write_backend_meta(model_dir, kind, repo_id=str(meta.get("repo_id") or ""))
        return kind

    def list_imported_models(self) -> list[dict[str, Any]]:
        state = self._read_runtime_state()
        active_model = state.get("active_model", "")
        imported_models = []

        self.runtime_model_root.mkdir(parents=True, exist_ok=True)
        for model_dir in sorted(self.runtime_model_root.iterdir(), key=lambda path: path.name.lower()):
            if not model_dir.is_dir():
                continue

            file_count = sum(
                1
                for item in model_dir.rglob("*")
                if item.is_file() and item.name != BACKEND_META_FILENAME
            )
            kind = self._ensure_backend_meta(model_dir)
            meta = self._read_backend_meta(model_dir)
            imported_models.append(
                {
                    "name": model_dir.name,
                    "path": str(model_dir),
                    "has_weights": (model_dir / "model.safetensors").exists(),
                    "file_count": file_count,
                    "is_active": model_dir.name == active_model,
                    "kind": kind,
                    "repo_id": str(meta.get("repo_id") or ""),
                }
            )

        return imported_models

    def get_active_model(self) -> dict[str, Any] | None:
        models = self.list_imported_models()
        for model in models:
            if model["is_active"]:
                return model
        return None

    def set_active_model(self, model_name: str) -> dict[str, Any]:
        normalized_name = self._sanitize_model_name(model_name)
        target_dir = self.runtime_model_root / normalized_name
        if not target_dir.exists() or not target_dir.is_dir():
            raise FileNotFoundError(f"模型不存在: {normalized_name}")

        state = self._read_runtime_state()
        state["active_model"] = normalized_name
        self._write_runtime_state(state)
        with self._model_lock:
            self._loaded_backend = None
            self._loaded_model_name = ""
        return {
            "status": "success",
            "active_model": normalized_name,
            "path": str(target_dir),
            "kind": self._ensure_backend_meta(target_dir),
        }

    def delete_model(self, model_name: str) -> dict[str, Any]:
        normalized_name = self._sanitize_model_name(model_name)
        target_dir = self.runtime_model_root / normalized_name
        if not target_dir.exists() or not target_dir.is_dir():
            raise FileNotFoundError(f"模型不存在: {normalized_name}")

        state = self._read_runtime_state()
        deleted_active = state.get("active_model") == normalized_name

        shutil.rmtree(target_dir)

        if deleted_active:
            state.pop("active_model", None)
            with self._model_lock:
                self._loaded_backend = None
                self._loaded_model_name = ""

        remaining_models = self.list_imported_models()
        next_active_model = None
        if remaining_models:
            next_active_model = remaining_models[0]["name"]
            state["active_model"] = next_active_model
        else:
            state.pop("active_model", None)

        self._write_runtime_state(state)

        return {
            "status": "success",
            "deleted_model": normalized_name,
            "deleted_active": deleted_active,
            "active_model": next_active_model,
        }

    def save_imported_model_file(self, model_name: str, relative_path: str, upload_file: UploadFile) -> dict[str, Any]:
        normalized_name = self._sanitize_model_name(model_name)
        sanitized_relative_path = self._sanitize_relative_path(relative_path)
        target_dir = self.runtime_model_root / normalized_name
        target_path = target_dir / sanitized_relative_path

        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            upload_file.file.seek(0)
        except (AttributeError, OSError):
            pass

        with target_path.open("wb") as file_obj:
            shutil.copyfileobj(upload_file.file, file_obj)

        # 关键文件落盘后嗅探一次 backend 类型并写入元数据，避免每次列出模型都走
        # 解析逻辑。Cohere 与 Qwen 仓库的 ``config.json`` 命中率最高，所以只在这
        # 个文件出现时刷新。
        if target_path.name == "config.json":
            self._ensure_backend_meta(target_dir)

        if self.get_active_model() is None:
            self.set_active_model(normalized_name)

        return {
            "status": "success",
            "model_name": normalized_name,
            "saved_path": str(target_path),
        }

    # ──────────────────────────────────────────────────────────────────────
    # Cohere Transcribe 远程下载
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_endpoint(endpoint: str | None) -> str:
        return str(endpoint or "").strip().rstrip("/")

    def _iter_download_endpoints(self) -> list[str]:
        configured = [
            self._normalize_endpoint(os.environ.get("ADBCONTROL_HF_ENDPOINT")),
            self._normalize_endpoint(os.environ.get("HF_ENDPOINT")),
        ]
        candidates = configured + [
            self._normalize_endpoint(ep) for ep in HF_MIRROR_ENDPOINTS
        ]

        ordered = []
        seen = set()
        for endpoint in candidates:
            if not endpoint or endpoint in seen:
                continue
            seen.add(endpoint)
            ordered.append(endpoint)
        return ordered

    @staticmethod
    def _summarize_download_error(exc: Exception) -> str:
        text = str(exc).strip().replace("\r", " ").replace("\n", " ")
        return text[:280] if text else exc.__class__.__name__

    def _create_download_tqdm(self, progress_queue):
        """创建一个自定义 tqdm 类，将进度推送到队列。"""
        from tqdm.auto import tqdm as base_tqdm

        class SseTqdm(base_tqdm):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._last_percent = -1

            def update(self, n=1):
                super().update(n)
                if self.total and self.total > 0:
                    percent = int(self.n / self.total * 100)
                    if percent != self._last_percent:
                        self._last_percent = percent
                        progress_queue.put({
                            "type": "progress",
                            "percent": percent,
                            "downloaded": self.n,
                            "total": self.total,
                            "desc": self.desc or "",
                        })

            def set_description(self, desc=None, refresh=True):
                super().set_description(desc, refresh)

        return SseTqdm

    def _download_with_progress(self, model_name, repo_id, kind, progress_queue):
        """带进度推送的下载生成器。"""
        from queue import Empty

        normalized_name = self._sanitize_model_name(model_name)
        effective_repo_id = str(repo_id).strip()

        if not self._dependency_available("huggingface_hub"):
            progress_queue.put({"type": "error", "message": "未安装 huggingface_hub，无法下载模型"})
            return

        try:
            from huggingface_hub import snapshot_download
        except ImportError as exc:
            progress_queue.put({"type": "error", "message": "未安装 huggingface_hub，无法下载模型"})
            return

        target_dir = self.runtime_model_root / normalized_name
        target_dir.mkdir(parents=True, exist_ok=True)

        progress_queue.put({"type": "info", "message": f"开始下载 {normalized_name}..."})

        download_endpoints = self._iter_download_endpoints()
        download_errors = []
        downloaded = False

        tqdm_class = self._create_download_tqdm(progress_queue)

        # 保存原始环境变量，下载完成后恢复
        original_hf_endpoint = os.environ.get("HF_ENDPOINT")

        for endpoint in download_endpoints:
            effective_endpoint = endpoint or DEFAULT_HF_DOWNLOAD_ENDPOINT
            progress_queue.put({"type": "info", "message": f"尝试端点: {effective_endpoint}"})

            # 通过环境变量强制设置镜像端点，确保所有内部 API 调用都使用镜像
            os.environ["HF_ENDPOINT"] = effective_endpoint

            attempt_kwargs = {
                "repo_id": effective_repo_id,
                "local_dir": str(target_dir),
                "local_dir_use_symlinks": False,
                "endpoint": effective_endpoint,
                "tqdm_class": tqdm_class,
            }
            try:
                snapshot_download(**attempt_kwargs)
                downloaded = True
                break
            except TypeError:
                attempt_kwargs.pop("local_dir_use_symlinks", None)
                attempt_kwargs.pop("tqdm_class", None)
                attempt_kwargs.pop("endpoint", None)
                try:
                    snapshot_download(**attempt_kwargs)
                    downloaded = True
                    break
                except Exception as exc:
                    download_errors.append((effective_endpoint, self._summarize_download_error(exc)))
            except Exception as exc:
                download_errors.append((effective_endpoint, self._summarize_download_error(exc)))

        # 恢复原始环境变量
        if original_hf_endpoint is None:
            os.environ.pop("HF_ENDPOINT", None)
        else:
            os.environ["HF_ENDPOINT"] = original_hf_endpoint

        if not downloaded:
            attempt_lines = "; ".join(
                f"{endpoint}: {message}"
                for endpoint, message in download_errors
            ) or "未记录具体错误"
            progress_queue.put({
                "type": "error",
                "message": (
                    f"下载模型失败（仓库 {effective_repo_id}）。"
                    f"已尝试端点：{'、'.join(download_endpoints) or DEFAULT_HF_DOWNLOAD_ENDPOINT}。"
                    f"详细错误：{attempt_lines}。"
                ),
            })
            return

        self._write_backend_meta(target_dir, kind, repo_id=effective_repo_id)

        if self.get_active_model() is None:
            self.set_active_model(normalized_name)

        progress_queue.put({
            "type": "done",
            "model_name": normalized_name,
            "path": str(target_dir),
            "repo_id": effective_repo_id,
            "kind": kind,
        })

    def download_cohere_transcribe(
        self,
        model_name: str = COHERE_DEFAULT_MODEL_NAME,
        repo_id: str = COHERE_DEFAULT_REPO_ID,
    ) -> dict[str, Any]:
        """从 HuggingFace 下载 Cohere Transcribe 到运行时目录。"""

        normalized_name = self._sanitize_model_name(model_name or COHERE_DEFAULT_MODEL_NAME)
        effective_repo_id = str(repo_id or COHERE_DEFAULT_REPO_ID).strip() or COHERE_DEFAULT_REPO_ID

        if not self._dependency_available("huggingface_hub"):
            raise AsrRuntimeError("未安装 huggingface_hub，无法下载 Cohere Transcribe 模型")

        try:
            from huggingface_hub import snapshot_download
        except ImportError as exc:
            raise AsrRuntimeError("未安装 huggingface_hub，无法下载 Cohere Transcribe 模型") from exc

        target_dir = self.runtime_model_root / normalized_name
        target_dir.mkdir(parents=True, exist_ok=True)

        download_endpoints = self._iter_download_endpoints()
        download_errors: list[tuple[str, str]] = []
        downloaded = False

        for endpoint in download_endpoints:
            attempt_kwargs = {
                "repo_id": effective_repo_id,
                "local_dir": str(target_dir),
                "local_dir_use_symlinks": False,
                "endpoint": endpoint,
            }
            try:
                snapshot_download(**attempt_kwargs)
                downloaded = True
                break
            except TypeError:
                # 旧版 huggingface_hub 不支持 ``local_dir_use_symlinks``
                attempt_kwargs.pop("local_dir_use_symlinks", None)
                try:
                    snapshot_download(**attempt_kwargs)
                    downloaded = True
                    break
                except Exception as exc:
                    download_errors.append((endpoint, self._summarize_download_error(exc)))
            except Exception as exc:
                download_errors.append((endpoint, self._summarize_download_error(exc)))

        if not downloaded:
            attempt_lines = "; ".join(
                f"{endpoint or DEFAULT_HF_DOWNLOAD_ENDPOINT}: {message}"
                for endpoint, message in download_errors
            ) or "未记录具体错误"
            raise AsrRuntimeError(
                f"下载 Cohere Transcribe 模型失败（仓库 {effective_repo_id}）。"
                f"已尝试端点：{'、'.join(download_endpoints) or DEFAULT_HF_DOWNLOAD_ENDPOINT}。"
                f"详细错误：{attempt_lines}。"
                "可设置 HF_ENDPOINT 或 ADBCONTROL_HF_ENDPOINT 环境变量切换镜像，"
                "或手动把模型文件放入运行时模型目录后再选择。"
            )

        self._write_backend_meta(target_dir, BACKEND_KIND_COHERE, repo_id=effective_repo_id)

        if self.get_active_model() is None:
            self.set_active_model(normalized_name)

        return {
            "status": "success",
            "model_name": normalized_name,
            "path": str(target_dir),
            "repo_id": effective_repo_id,
            "kind": BACKEND_KIND_COHERE,
        }

    def get_status(self) -> dict[str, Any]:
        qwen_models = []
        if self.qwen_root.exists() and self.qwen_root.is_dir():
            for model_dir in sorted(self.qwen_root.iterdir(), key=lambda path: path.name.lower()):
                if model_dir.is_dir():
                    qwen_models.append(
                        {
                            "name": model_dir.name,
                            "path": str(model_dir),
                            "has_weights": (model_dir / "model.safetensors").exists(),
                        }
                    )

        case_dir = self.case_root
        references_dir = self.reference_root
        audio_dir = self.voice_project_root / "audio"
        results_dir = self.voice_project_root / "results"
        active_project_root = self.project_root if self.project_root.exists() else self.bundle_project_root
        active_voice_project_root = self.voice_project_root if self.voice_project_root.exists() else self.bundle_voice_project_root

        case_files = self._list_files(case_dir, ("*.xlsx", "*.xls"))
        reference_files = self._list_files(references_dir, ("*.txt",))
        audio_files = self._list_files(audio_dir, ("*.wav", "*.mp3", "*.flac", "*.m4a"))
        result_files = self._list_files(results_dir, ("*.txt", "*.json"))
        imported_models = self.list_imported_models()
        active_model = self.get_active_model()
        dependency_status = self.get_runtime_dependency_status()

        return {
            "project_exists": active_project_root.exists(),
            "project_root": str(active_project_root),
            "voice_project_exists": active_voice_project_root.exists(),
            "voice_project_root": str(active_voice_project_root),
            "qwen_root": str(self.qwen_root),
            "qwen_models": qwen_models,
            "runtime_model_root": str(self.runtime_model_root),
            "imported_models": imported_models,
            "active_model": active_model,
            "case_files": case_files,
            "reference_count": len(reference_files),
            "audio_count": len(audio_files),
            "result_count": len(result_files),
            "dependencies": dependency_status,
            "reference_root": str(self.reference_root),
            "audio_root": str(self.audio_root),
            "result_root": str(self.result_root),
            "recommended_remote_models": [
                {
                    "kind": BACKEND_KIND_COHERE,
                    "name": COHERE_DEFAULT_MODEL_NAME,
                    "repo_id": COHERE_DEFAULT_REPO_ID,
                    "description": "Cohere Transcribe（2B Conformer，14 语言）",
                },
            ],
        }


asr_service = AsrService()