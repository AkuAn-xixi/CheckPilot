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

#: 三种后端类型常量
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

#: 通过 HuggingFace 镜像下载时的端点候选，国内优先。
DEFAULT_HF_DOWNLOAD_ENDPOINT = "https://hf-mirror.com"
MIRROR_HF_DOWNLOAD_ENDPOINTS = ("https://huggingface.co",)


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
            import soundfile as sf
            import scipy.signal

            waveform, sr = sf.read(str(audio_path), dtype="float32")
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
                raise AsrRuntimeError("未安装 soundfile/scipy 或 librosa，无法读取音频") from exc
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
            self.recording_data.append(indata.copy())

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
        if self.stream is None:
            return

        try:
            self.stream.stop()
            self.stream.close()
        finally:
            self.stream = None

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

    @staticmethod
    def clean_text(text: str) -> str:
        text = str(text or "").lower()
        text = re.sub(r"[^\w\s]", "", text)
        return re.sub(r"\s+", " ", text).strip()

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
                "当前运行的是打包版 ADBControl.exe，不能通过给 exe 外部执行 pip install 直接补进已打包依赖。",
                "请在用于执行 build_exe.bat 的 Python 环境中，先执行 python -m pip install -U pip。",
            ]
            install_steps.extend([f"在打包环境执行: {command}" for command in install_commands])
            install_steps.append("重新运行 build_exe.bat 生成新的 ADBControl.exe，并替换当前 dist 目录中的程序。")
            install_steps.append("重启新的 ADBControl.exe 后，再回到当前页面点击“刷新状态”。")
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
            self._normalize_endpoint(DEFAULT_HF_DOWNLOAD_ENDPOINT),
            *[self._normalize_endpoint(item) for item in MIRROR_HF_DOWNLOAD_ENDPOINTS],
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
                }
            ],
        }


asr_service = AsrService()