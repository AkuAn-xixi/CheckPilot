"""ASR 资源探测与运行服务模块"""
import json
import math
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


class AsrRuntimeError(RuntimeError):
    """Raised when ASR runtime dependencies or execution are unavailable."""


class Recorder:
    """Minimal audio recorder used by the ASR execution flow."""

    def __init__(self, sample_rate: int = 44100, channels: int = 1, device: int | None = None):
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self.recording_data: list[np.ndarray] = []
        self.stream = None

    def start_recording(self) -> None:
        try:
            import sounddevice as sounddevice
        except ImportError as exc:
            raise AsrRuntimeError("未安装 sounddevice，无法录音") from exc

        self.recording_data = []

        def callback(indata, frames, time_info, status):
            if status:
                return
            self.recording_data.append(indata.copy())

        try:
            self.stream = sounddevice.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                callback=callback,
                device=self.device,
            )
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
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes((recording * 32767).astype(np.int16).tobytes())

        return output_path


class TextComparer:
    """Text similarity helper reused by the backend ASR flow."""

    @staticmethod
    def clean_text(text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip()

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
        self.voice_project_root = self.project_root / "voice_recorder_compare"
        self.qwen_root = self.project_root / "Qwen"
        self.runtime_model_root = settings.ASR_MODELS_DIR
        self.runtime_state_file = settings.WORKING_DIR / "asr_runtime_state.json"
        self.reference_root = self.voice_project_root / "references"
        self.audio_root = self.voice_project_root / "audio"
        self.result_root = self.voice_project_root / "results"
        self._loaded_model = None
        self._loaded_model_name = ""
        self._model_lock = Lock()

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

    def _dependency_available(self, module_name: str) -> bool:
        try:
            __import__(module_name)
        except ImportError:
            return False
        return True

    def get_runtime_dependency_status(self) -> dict[str, Any]:
        available = {
            "sounddevice": self._dependency_available("sounddevice"),
            "qwen_asr": self._dependency_available("qwen_asr"),
            "torch": self._dependency_available("torch"),
        }

        missing = [name for name, is_available in available.items() if not is_available]
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        install_commands = []
        if "qwen_asr" in missing:
            install_commands.append("python -m pip install -U qwen-asr")
        if "sounddevice" in missing:
            install_commands.append("python -m pip install -U sounddevice")
        if "torch" in missing:
            install_commands.append("python -m pip install torch --index-url https://download.pytorch.org/whl/cpu")

        install_steps = [
            "建议使用独立的 Python 3.12 虚拟环境安装 ASR 依赖，避免与当前项目环境冲突。",
            "进入该环境后，先执行 python -m pip install -U pip。",
        ]
        install_steps.extend([f"执行: {command}" for command in install_commands])
        install_steps.append("安装完成后重启后端服务，再回到当前页面点击“刷新状态”。")

        notes = []
        if sys.version_info >= (3, 14):
            notes.append(
                f"当前后端运行在 Python {python_version}。qwen-asr 官方更推荐使用新的 Python 3.12 环境。"
            )

        return {
            "available": available,
            "ready": not missing,
            "missing": missing,
            "python_version": python_version,
            "recommended_python_version": "3.12",
            "install_commands": install_commands,
            "install_steps": install_steps,
            "notes": notes,
            "restart_required": bool(missing),
        }

    def create_recorder(self, device: int | None = None) -> Recorder:
        return Recorder(device=device)

    def _load_runtime_model(self):
        active_model = self.get_active_model()
        if active_model is None:
            raise AsrRuntimeError("请先导入并选择 ASR 模型")

        model_name = active_model["name"]
        model_path = Path(active_model["path"])
        with self._model_lock:
            if self._loaded_model is not None and self._loaded_model_name == model_name:
                return self._loaded_model

            try:
                import torch
                from qwen_asr import Qwen3ASRModel
            except ImportError as exc:
                raise AsrRuntimeError("未安装 qwen_asr 或 torch，无法执行语音识别") from exc

            device = "cuda:0" if torch.cuda.is_available() else "cpu"
            dtype = torch.float16 if device.startswith("cuda") else torch.float32
            batch_size = 8 if device.startswith("cuda") else 1

            try:
                model = Qwen3ASRModel.from_pretrained(
                    str(model_path),
                    dtype=dtype,
                    device_map=device,
                    max_inference_batch_size=batch_size,
                )
            except Exception as exc:
                raise AsrRuntimeError(f"加载 ASR 模型失败: {str(exc)}") from exc

            self._loaded_model = model
            self._loaded_model_name = model_name
            return model

    def transcribe_audio(self, audio_path: str | Path, language: str = "English") -> str:
        model = self._load_runtime_model()
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

    def list_imported_models(self) -> list[dict[str, Any]]:
        state = self._read_runtime_state()
        active_model = state.get("active_model", "")
        imported_models = []

        self.runtime_model_root.mkdir(parents=True, exist_ok=True)
        for model_dir in sorted(self.runtime_model_root.iterdir(), key=lambda path: path.name.lower()):
            if not model_dir.is_dir():
                continue

            file_count = sum(1 for item in model_dir.rglob("*") if item.is_file())
            imported_models.append(
                {
                    "name": model_dir.name,
                    "path": str(model_dir),
                    "has_weights": (model_dir / "model.safetensors").exists(),
                    "file_count": file_count,
                    "is_active": model_dir.name == active_model,
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
            self._loaded_model = None
            self._loaded_model_name = ""
        return {
            "status": "success",
            "active_model": normalized_name,
            "path": str(target_dir),
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
                self._loaded_model = None
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

        if self.get_active_model() is None:
            self.set_active_model(normalized_name)

        return {
            "status": "success",
            "model_name": normalized_name,
            "saved_path": str(target_path),
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

        case_dir = self.voice_project_root / "case"
        references_dir = self.voice_project_root / "references"
        audio_dir = self.voice_project_root / "audio"
        results_dir = self.voice_project_root / "results"

        case_files = self._list_files(case_dir, ("*.xlsx", "*.xls"))
        reference_files = self._list_files(references_dir, ("*.txt",))
        audio_files = self._list_files(audio_dir, ("*.wav", "*.mp3", "*.flac", "*.m4a"))
        result_files = self._list_files(results_dir, ("*.txt", "*.json"))
        imported_models = self.list_imported_models()
        active_model = self.get_active_model()
        dependency_status = self.get_runtime_dependency_status()

        return {
            "project_exists": self.project_root.exists(),
            "project_root": str(self.project_root),
            "voice_project_exists": self.voice_project_root.exists(),
            "voice_project_root": str(self.voice_project_root),
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
        }


asr_service = AsrService()