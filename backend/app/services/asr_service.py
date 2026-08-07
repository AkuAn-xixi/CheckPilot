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

    def transcribe(self, audio_path: str | Path, language: str = "English") -> str:
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

    def transcribe(self, audio_path: str | Path, language: str = "English") -> str:
        model = self._load()
        try:
            results = model.transcribe(audio=str(audio_path), language=language)
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

    def transcribe(self, audio_path: str | Path, language: str = "English") -> str:
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
        if not self.recording_data:
            raise AsrRuntimeError("录音结果为空，未采集到音频数据")

        recording = np.concatenate(self.recording_data, axis=0)
        duration = len(recording) / self.sample_rate
        max_amp = float(np.max(np.abs(recording)))
        _log.info(
            "[录音] 保存: 时长=%.2fs, 最大振幅=%.6f, 数据块=%d, 设备=%s",
            duration, max_amp, len(self.recording_data), self.device
        )

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(self.actual_channels)
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
        # 应用用户自定义替换规则（在标点移除和数字转换之前）
        text = TextComparer.apply_substitutions(text)
        # 将 "+" 和单词中的 "plus" 统一为分词 "plus"，确保 "Whale+" 和 "WhalePlus" 视为相同
        text = re.sub(r"\+", " plus ", text)
        text = re.sub(r"(\w)(plus)", r"\1 plus ", text)
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

    def transcribe_audio(self, audio_path: str | Path, language: str = "English") -> str:
        backend = self._load_runtime_model()
        return backend.transcribe(audio_path, language=language)

    def save_audio_recording(self, recorder: Recorder, case_title: str) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_path = self.audio_root / f"recording_{self._sanitize_case_name(case_title)}_{timestamp}.wav"
        return recorder.save_recording(target_path)

    @staticmethod
    def enhance_audio(audio_path: str | Path, target_db: float = -20.0, voice_boost: bool = True) -> Path:
        """音频增强：音量归一化 + 人声频段增强，原地替换。

        Args:
            audio_path: WAV 文件路径
            target_db: 目标音量（dB），默认 -20 dB
            voice_boost: 是否增强人声频段（300Hz-3kHz），默认 True
        """
        from scipy.io import wavfile
        from scipy.signal import butter, filtfilt

        audio_path = Path(audio_path)

        # 读取音频
        sr, raw_data = wavfile.read(str(audio_path))
        data = raw_data.astype(np.float64)
        original_dtype = raw_data.dtype

        # 归一化到 [-1, 1]
        if np.issubdtype(original_dtype, np.integer):
            max_val = np.iinfo(original_dtype).max
            data = data / max_val

        # 转为单声道处理
        is_stereo = data.ndim > 1
        if is_stereo:
            data_mono = data.mean(axis=1)
        else:
            data_mono = data.copy()

        # 1. 音量归一化
        current_rms = np.sqrt(np.mean(data_mono ** 2))
        if current_rms > 1e-6:  # 避免除以零
            target_rms = 10 ** (target_db / 20)
            gain = target_rms / current_rms
            # 限制增益范围，避免过度放大。上限放宽到 200 倍以覆盖采集卡等
            # 极弱信号（-60dB 级）录音，否则归一化后仍停留在 -50dB 附近无法识别。
            gain = min(gain, 200.0)  # 最大放大 200 倍
            gain = max(gain, 0.1)    # 最小缩小到 0.1 倍
            data_mono = data_mono * gain
            _log.info("[增强] 音量归一化: 增益=%.2f (原始 RMS=%.4f, 目标 RMS=%.4f)", gain, current_rms, target_rms)

        # 2. 人声频段增强（带通滤波 + 增益叠加）
        if voice_boost and sr > 6000:  # 采样率太低时跳过
            # 设计带通滤波器：300Hz - 3kHz（人声主要频段）
            low_freq = 300 / (sr / 2)
            high_freq = min(3000 / (sr / 2), 0.95)  # 不超过奈奎斯特频率

            if low_freq < high_freq:
                b, a = butter(4, [low_freq, high_freq], btype='band')
                voice_band = filtfilt(b, a, data_mono)
                # 将人声频段叠加到原信号（增益 0.3）
                data_mono = data_mono + 0.3 * voice_band
                _log.info("[增强] 人声频段增强: 300Hz-3kHz, 增益=0.3")

        # 防止削波
        data_mono = np.clip(data_mono, -1.0, 1.0)

        # 如果是立体声，将增强后的单声道应用到所有通道
        if is_stereo:
            # 保持原始的立体声平衡
            gain_ratio = data_mono / (data.mean(axis=1) + 1e-10)
            gain_ratio = np.clip(gain_ratio, 0.1, 10.0)
            data = data * gain_ratio[:, np.newaxis]
            data = np.clip(data, -1.0, 1.0)
        else:
            data = data_mono

        # 转换回原始数据类型并写入
        if np.issubdtype(original_dtype, np.integer):
            data = (data * max_val).astype(original_dtype)
        else:
            data = data.astype(original_dtype)

        wavfile.write(str(audio_path), sr, data)
        duration = len(data) / sr
        _log.info("[增强] 完成: %s (采样率=%d, 时长=%.2fs)", audio_path.name, sr, duration)
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
        """对 WAV 文件做离线降噪（频谱门控），原地替换。若 noisereduce 未安装则跳过。"""
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
        data = raw_data.astype(np.float64)
        # 归一化整数格式到 [-1, 1] 范围
        if np.issubdtype(raw_data.dtype, np.integer):
            data = data / np.iinfo(raw_data.dtype).max
        # 转为单声道处理
        if data.ndim > 1:
            data = data.mean(axis=1)
        reduced = nr.reduce_noise(y=data, sr=sr, stationary=False)
        sf.write(str(audio_path), reduced, sr)
        _log.info("[降噪] 完成: %s (采样率=%d, 时长=%.2fs)", audio_path.name, sr, len(reduced) / sr)
        return audio_path

    @staticmethod
    def adjust_speed(audio_path: str | Path, speed: float = 0.9) -> Path:
        """调整音频播放速度，原地替换。使用 librosa 或 scipy 实现。

        Args:
            audio_path: WAV 文件路径
            speed: 播放速度倍数，< 1 表示减速，> 1 表示加速。默认 0.9 倍速。
        """
        if speed <= 0:
            raise ValueError(f"速度倍数必须大于 0，当前值: {speed}")

        # 接近 1.0 时跳过处理
        if abs(speed - 1.0) < 0.01:
            return Path(audio_path)

        audio_path = Path(audio_path)

        # 尝试用 librosa 实现（质量更好）
        try:
            import librosa
            import soundfile as sf

            data, sr = librosa.load(str(audio_path), sr=None, mono=False)
            # librosa.effects.time_stretch 需要单声道
            if data.ndim > 1:
                # 立体声：分别处理每个通道再合并
                channels = []
                for ch in range(data.shape[0]):
                    stretched = librosa.effects.time_stretch(data[ch], rate=speed)
                    channels.append(stretched)
                result = np.stack(channels, axis=0)
            else:
                result = librosa.effects.time_stretch(data, rate=speed)

            sf.write(str(audio_path), result.T if result.ndim > 1 else result, sr)
            duration = len(result) / sr if result.ndim == 1 else result.shape[1] / sr
            _log.info("[变速] 完成: %s (速度=%.2f, 采样率=%d, 时长=%.2fs)", audio_path.name, speed, sr, duration)
            return audio_path
        except ImportError:
            pass

        # 备选：使用 scipy 的简单重采样实现（改变速度同时改变音调）
        try:
            from scipy.io import wavfile
            from scipy.signal import resample_poly
            from math import gcd

            sr, raw_data = wavfile.read(str(audio_path))
            # 计算重采样比例：speed < 1 时减速（样本变多），speed > 1 时加速（样本变少）
            new_sr = int(sr * speed)
            g = gcd(new_sr, sr)
            stretched = resample_poly(raw_data, sr // g, new_sr // g)

            # 保持原始数据类型
            if np.issubdtype(raw_data.dtype, np.integer):
                max_val = np.iinfo(raw_data.dtype).max
                stretched = np.clip(stretched, -max_val, max_val).astype(raw_data.dtype)

            wavfile.write(str(audio_path), sr, stretched)
            _log.info("[变速] 完成: %s (速度=%.2f, 采样率=%d, 时长=%.2fs)", audio_path.name, speed, sr, len(stretched) / sr)
            return audio_path
        except Exception as exc:
            _log.warning("[变速] 处理失败，跳过: %s", exc)
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