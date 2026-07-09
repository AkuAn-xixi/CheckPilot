"""图片比对调度与 DINOv2 模型管理服务。"""
import base64
import importlib
import importlib.util
import json
import logging
import os
import re
import shutil
import sys
from pathlib import Path
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

import cv2
import numpy as np

from ..config import settings
from .image_service import (
    ImageVerifier,
    verify_image_base64_match as verify_image_base64_match_opencv,
    verify_image_match as verify_image_match_opencv,
)


class ImageCompareRuntimeError(RuntimeError):
    """Raised when the selected image comparison runtime cannot be used."""


class ImageCompareService:
    """Manage optional DINOv2 models and dispatch image comparison requests."""

    DEFAULT_MODEL_NAME = "DINOv2-Base"
    DEFAULT_REPO_ID = "facebook/dinov2-base"
    MODEL_META_FILENAME = "model_meta.json"
    DEFAULT_DOWNLOAD_ENDPOINT = "https://hf-mirror.com"
    MIRROR_DOWNLOAD_ENDPOINTS = ("https://huggingface.co",)

    def __init__(self) -> None:
        self.runtime_model_root = settings.IMAGE_MODELS_DIR
        self.runtime_state_file = settings.WORKING_DIR / "image_compare_runtime_state.json"
        self._loaded_model = None
        self._loaded_processor = None
        self._loaded_model_name = ""
        self._loaded_device = "cpu"
        self._model_lock = Lock()

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

    @staticmethod
    def _normalize_endpoint(endpoint: str | None) -> str:
        return str(endpoint or "").strip().rstrip("/")

    def _iter_download_endpoints(self) -> list[str]:
        configured = [
            self._normalize_endpoint(os.environ.get("ADBCONTROL_HF_ENDPOINT")),
            self._normalize_endpoint(os.environ.get("HF_ENDPOINT")),
        ]
        candidates = configured + [
            self._normalize_endpoint(self.DEFAULT_DOWNLOAD_ENDPOINT),
            *[self._normalize_endpoint(item) for item in self.MIRROR_DOWNLOAD_ENDPOINTS],
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

    def _build_download_failure_message(
        self,
        repo_id: str,
        endpoints: list[str],
        errors: list[tuple[str, str]],
        target_dir: Path,
    ) -> str:
        attempt_lines = []
        for endpoint, message in errors:
            endpoint_label = endpoint or self.DEFAULT_DOWNLOAD_ENDPOINT
            attempt_lines.append(f"{endpoint_label}: {message}")

        attempted_text = "；".join(attempt_lines) if attempt_lines else "未记录具体错误"
        endpoints_text = "、".join(endpoints) if endpoints else self.DEFAULT_DOWNLOAD_ENDPOINT
        manual_hint = (
            f"当前默认会优先尝试国内镜像 {self.DEFAULT_DOWNLOAD_ENDPOINT}。"
            f"如果你所在环境需要其他镜像，可设置环境变量 HF_ENDPOINT 或 ADBCONTROL_HF_ENDPOINT；"
            f"或者手动将模型文件下载到 {target_dir} 后再选择模型。"
        )
        return (
            f"下载 DINOv2 模型失败，仓库为 {repo_id}。"
            f"已尝试以下下载端点：{endpoints_text}。"
            f"详细错误：{attempted_text}。"
            f"{manual_hint}"
        )

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

    def get_runtime_dependency_status(self) -> dict[str, Any]:
        dependency_details = {
            "torch": self._inspect_dependency("torch"),
            "transformers": self._inspect_dependency("transformers"),
            "huggingface_hub": self._inspect_dependency("huggingface_hub"),
        }
        available = {
            name: bool(details["available"])
            for name, details in dependency_details.items()
        }

        missing = [name for name, is_available in available.items() if not is_available]
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        is_frozen_runtime = bool(getattr(sys, "frozen", False))

        install_commands = []
        if "transformers" in missing or "huggingface_hub" in missing:
            install_commands.append("python -m pip install -U transformers huggingface_hub safetensors")
        if "torch" in missing:
            install_commands.append("python -m pip install torch --index-url https://download.pytorch.org/whl/cpu")

        if missing and is_frozen_runtime:
            install_steps = [
                "当前运行的是打包版 ADBControl.exe，不能直接给 exe 外部补装 DINOv2 依赖。",
                "请在用于执行 build_exe.bat 的 Python 环境中先执行 python -m pip install -U pip。",
            ]
            install_steps.extend([f"在打包环境执行: {command}" for command in install_commands])
            install_steps.append("重新运行 build_exe.bat 生成新的 ADBControl.exe，并替换当前 dist 目录中的程序。")
            install_steps.append("重启新的 ADBControl.exe 后，再回到当前页面点击“刷新状态”。")
        else:
            install_steps = [
                "DINOv2 依赖是可选项；若不安装，图片校验仍可继续使用默认 OpenCV。",
                "如需启用 DINOv2，请在当前 Python 3.12 环境先执行 python -m pip install -U pip。",
            ]
            install_steps.extend([f"执行: {command}" for command in install_commands])
            if install_commands:
                install_steps.append("安装完成后重启后端服务，再回到当前页面点击“刷新状态”。")

        notes = []
        for details in dependency_details.values():
            error_text = str(details.get("error") or "").strip()
            if error_text:
                notes.append(error_text)
        if is_frozen_runtime:
            notes.append(f"当前后端运行在打包版进程中: {sys.executable}")

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

    def _reset_loaded_model(self) -> None:
        with self._model_lock:
            self._loaded_model = None
            self._loaded_processor = None
            self._loaded_model_name = ""
            self._loaded_device = "cpu"

    def _model_meta_path(self, model_dir: Path) -> Path:
        return model_dir / self.MODEL_META_FILENAME

    def _load_model_meta(self, model_dir: Path) -> dict[str, Any]:
        meta_path = self._model_meta_path(model_dir)
        if not meta_path.exists():
            return {}
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_model_meta(self, model_dir: Path, data: dict[str, Any]) -> None:
        meta_path = self._model_meta_path(model_dir)
        meta_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _has_model_weights(self, model_dir: Path) -> bool:
        return any(
            (model_dir / filename).exists()
            for filename in ("model.safetensors", "pytorch_model.bin", "tf_model.h5")
        ) and (model_dir / "config.json").exists()

    def list_imported_models(self) -> list[dict[str, Any]]:
        state = self._read_runtime_state()
        active_model = state.get("active_model", "")
        imported_models = []

        self.runtime_model_root.mkdir(parents=True, exist_ok=True)
        for model_dir in sorted(self.runtime_model_root.iterdir(), key=lambda path: path.name.lower()):
            if not model_dir.is_dir():
                continue

            file_count = sum(1 for item in model_dir.rglob("*") if item.is_file())
            metadata = self._load_model_meta(model_dir)
            imported_models.append(
                {
                    "name": model_dir.name,
                    "path": str(model_dir),
                    "file_count": file_count,
                    "repo_id": metadata.get("repo_id", ""),
                    "is_active": model_dir.name == active_model,
                    "has_weights": self._has_model_weights(model_dir),
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
        self._reset_loaded_model()
        logger.info("[模型] 已切换活动模型: %s", normalized_name)

        return {
            "status": "success",
            "active_model": normalized_name,
            "path": str(target_dir),
            "compare_backend": "dinov2",
        }

    def clear_active_model(self) -> dict[str, Any]:
        state = self._read_runtime_state()
        state.pop("active_model", None)
        self._write_runtime_state(state)
        self._reset_loaded_model()
        logger.info("[模型] 已清除活动模型，回退为 OpenCV")
        return {
            "status": "success",
            "active_model": None,
            "compare_backend": "opencv",
        }

    def delete_model(self, model_name: str) -> dict[str, Any]:
        normalized_name = self._sanitize_model_name(model_name)
        target_dir = self.runtime_model_root / normalized_name
        if not target_dir.exists() or not target_dir.is_dir():
            raise FileNotFoundError(f"模型不存在: {normalized_name}")

        state = self._read_runtime_state()
        deleted_active = state.get("active_model") == normalized_name
        shutil.rmtree(target_dir)
        logger.info("[模型] 已删除模型: %s (was_active=%s)", normalized_name, deleted_active)

        if deleted_active:
            state.pop("active_model", None)
            self._reset_loaded_model()

        self._write_runtime_state(state)
        return {
            "status": "success",
            "deleted_model": normalized_name,
            "deleted_active": deleted_active,
            "active_model": None if deleted_active else state.get("active_model"),
            "compare_backend": "opencv" if deleted_active else ("dinov2" if state.get("active_model") else "opencv"),
        }

    def download_model(self, model_name: str = "", repo_id: str = "") -> dict[str, Any]:
        normalized_name = self._sanitize_model_name(model_name or self.DEFAULT_MODEL_NAME)
        effective_repo_id = str(repo_id or self.DEFAULT_REPO_ID).strip() or self.DEFAULT_REPO_ID
        target_dir = self.runtime_model_root / normalized_name
        logger.info("[模型] 开始下载模型: name=%s, repo=%s, target=%s", normalized_name, effective_repo_id, target_dir)

        dependency_status = self.get_runtime_dependency_status()
        required_missing = [
            name
            for name in dependency_status["missing"]
            if name in {"torch", "transformers", "huggingface_hub"}
        ]
        if required_missing:
            missing_text = ", ".join(required_missing)
            raise ImageCompareRuntimeError(f"DINOv2 下载依赖缺失: {missing_text}")

        try:
            from huggingface_hub import snapshot_download
        except ImportError as exc:
            raise ImageCompareRuntimeError("未安装 huggingface_hub，无法下载 DINOv2 模型") from exc

        target_dir.mkdir(parents=True, exist_ok=True)

        download_kwargs = {
            "repo_id": effective_repo_id,
            "local_dir": str(target_dir),
            "local_dir_use_symlinks": False,
        }
        download_endpoints = self._iter_download_endpoints()
        download_errors: list[tuple[str, str]] = []
        downloaded = False

        for endpoint in download_endpoints:
            attempt_kwargs = dict(download_kwargs)
            attempt_kwargs["endpoint"] = endpoint
            try:
                snapshot_download(**attempt_kwargs)
                downloaded = True
                break
            except TypeError:
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
            if not self._has_model_weights(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
            logger.error("[模型] 下载失败: %s, errors=%s", normalized_name, download_errors)
            raise ImageCompareRuntimeError(
                self._build_download_failure_message(
                    repo_id=effective_repo_id,
                    endpoints=download_endpoints,
                    errors=download_errors,
                    target_dir=target_dir,
                )
            )

        self._write_model_meta(
            target_dir,
            {
                "name": normalized_name,
                "repo_id": effective_repo_id,
                "kind": "dinov2",
            },
        )
        logger.info("[模型] 下载成功: %s -> %s", normalized_name, target_dir)

        return {
            "status": "success",
            "model_name": normalized_name,
            "path": str(target_dir),
            "repo_id": effective_repo_id,
            "active_model": self.get_active_model(),
            "compare_backend": "dinov2" if self.get_active_model() else "opencv",
        }

    def get_status(self) -> dict[str, Any]:
        imported_models = self.list_imported_models()
        active_model = self.get_active_model()
        dependency_status = self.get_runtime_dependency_status()

        return {
            "runtime_model_root": str(self.runtime_model_root),
            "imported_models": imported_models,
            "active_model": active_model,
            "compare_backend": "dinov2" if active_model else "opencv",
            "dependencies": dependency_status,
            "recommended_model": {
                "name": self.DEFAULT_MODEL_NAME,
                "repo_id": self.DEFAULT_REPO_ID,
            },
        }

    def _load_runtime_model(self):
        active_model = self.get_active_model()
        if active_model is None:
            raise ImageCompareRuntimeError("当前未选择 DINOv2 模型，系统将继续使用 OpenCV")

        model_name = active_model["name"]
        model_path = Path(active_model["path"])

        with self._model_lock:
            if (
                self._loaded_model is not None
                and self._loaded_processor is not None
                and self._loaded_model_name == model_name
            ):
                return self._loaded_processor, self._loaded_model, self._loaded_device

            try:
                import torch
                from transformers import AutoImageProcessor, AutoModel
            except ImportError as exc:
                raise ImageCompareRuntimeError("未安装 torch 或 transformers，无法启用 DINOv2 图片比对") from exc

            device = "cuda" if torch.cuda.is_available() else "cpu"
            try:
                processor = AutoImageProcessor.from_pretrained(str(model_path), local_files_only=True)
                model = AutoModel.from_pretrained(str(model_path), local_files_only=True)
                model.to(device)
                model.eval()
            except Exception as exc:
                raise ImageCompareRuntimeError(f"加载 DINOv2 模型失败: {str(exc)}") from exc

            self._loaded_processor = processor
            self._loaded_model = model
            self._loaded_model_name = model_name
            self._loaded_device = device
            return processor, model, device

    def _prepare_inputs(self, first_image, second_image):
        try:
            import torch
            from torch.nn import functional as F
        except ImportError as exc:
            raise ImageCompareRuntimeError("未安装 torch，无法执行 DINOv2 比对") from exc

        processor, model, device = self._load_runtime_model()
        first_rgb = cv2.cvtColor(first_image, cv2.COLOR_BGR2RGB)
        second_rgb = cv2.cvtColor(second_image, cv2.COLOR_BGR2RGB)
        inputs = processor(images=[first_rgb, second_rgb], return_tensors="pt")
        inputs = {key: value.to(device) for key, value in inputs.items()}

        with torch.inference_mode():
            outputs = model(**inputs)

        embeddings = getattr(outputs, "pooler_output", None)
        if embeddings is None:
            last_hidden_state = getattr(outputs, "last_hidden_state", None)
            if last_hidden_state is None:
                raise ImageCompareRuntimeError("DINOv2 模型未返回可用特征")

            cls_embeddings = last_hidden_state[:, 0]
            if last_hidden_state.size(1) > 1:
                patch_embeddings = last_hidden_state[:, 1:].mean(dim=1)
                embeddings = (cls_embeddings + patch_embeddings) / 2.0
            else:
                embeddings = cls_embeddings

        embeddings = F.normalize(embeddings, dim=-1)
        similarity = F.cosine_similarity(embeddings[0].unsqueeze(0), embeddings[1].unsqueeze(0)).item()
        return float(max(0.0, min(1.0, (similarity + 1.0) / 2.0)))

    def _verify_with_opencv_path(self, screen_img_path: str, icon_img_path: str, threshold: float = 0.9) -> dict[str, Any]:
        result = verify_image_match_opencv(screen_img_path, icon_img_path, threshold)
        result.setdefault("engine", "opencv")
        result.setdefault("model_name", "")
        logger.info("[比对] OpenCV 比对完成: matched=%s, score=%.4f", result.get('matched'), result.get('score', 0.0))
        return result

    def _verify_with_opencv_base64(self, screen_img_path: str, icon_img_base64: str, threshold: float = 0.9) -> dict[str, Any]:
        result = verify_image_base64_match_opencv(screen_img_path, icon_img_base64, threshold)
        result.setdefault("engine", "opencv")
        result.setdefault("model_name", "")
        logger.info("[比对] OpenCV(base64) 比对完成: matched=%s, score=%.4f", result.get('matched'), result.get('score', 0.0))
        return result

    def _verify_with_dinov2_arrays(self, img_screen, img_icon, threshold: float = 0.9) -> dict[str, Any]:
        active_model = self.get_active_model()
        if active_model is None:
            raise ImageCompareRuntimeError("当前未选择 DINOv2 模型")

        match = ImageVerifier._best_subimage_match(img_screen, img_icon)
        x, y = match["loc"]
        w, h = match["size"]
        roi = img_screen[y:y + h, x:x + w]
        reference_patch = match["reference"]
        if roi is None or reference_patch is None or roi.size == 0 or reference_patch.size == 0:
            raise ImageCompareRuntimeError("无法从截图中提取有效的候选区域")

        template_score = float(match.get("template_score", 0.0))
        structure_score = float(
            match.get("post_structure_score")
            if match.get("post_structure_score") is not None
            else ImageVerifier.calc_structure_similarity(roi, reference_patch)
        )
        feature_score = float(
            match.get("post_feature_score")
            if match.get("post_feature_score") is not None
            else ImageVerifier.calc_feature_similarity(roi, reference_patch)
        )
        color_score = float(
            match.get("post_color_score")
            if match.get("post_color_score") is not None
            else ImageVerifier.calc_color_hist_similarity(roi, reference_patch)
        )
        dino_score = self._prepare_inputs(roi, reference_patch)
        logger.info("[比对] DINOv2 分数明细: template=%.4f, structure=%.4f, feature=%.4f, color=%.4f, dino=%.4f",
                    template_score, structure_score, feature_score, color_score, dino_score)

        required_score = float(threshold)
        combined_score = max(
            dino_score,
            dino_score * 0.82 + template_score * 0.18,
            dino_score * 0.72 + structure_score * 0.18 + color_score * 0.10,
        )
        matched = combined_score >= required_score and (
            template_score >= 0.45 or (template_score >= 0.35 and structure_score >= 0.55)
        )
        logger.info("[比对] DINOv2 判定: combined=%.4f, required=%.4f, matched=%s",
                    combined_score, required_score, matched)

        return {
            "success": True,
            "matched": matched,
            "score": float(max(0.0, min(1.0, combined_score))),
            "template_score": template_score,
            "struct_score": structure_score,
            "color_score": color_score,
            "feature_score": feature_score,
            "aspect_ratio_score": 1.0,
            "structure_score": structure_score,
            "local_structure_score": structure_score,
            "dino_score": float(max(0.0, min(1.0, dino_score))),
            "engine": "dinov2",
            "model_name": active_model["name"],
            "message": "验证成功" if matched else "验证失败",
        }

    @staticmethod
    def _decode_base64_image(image_base64: str):
        payload = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
        image_bytes = base64.b64decode(payload)
        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        return cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    def verify(self, screen_img_path: str, icon_img_path: str, threshold: float = 0.9) -> dict[str, Any]:
        active_model = self.get_active_model()
        if active_model is None:
            logger.info("[比对] 使用 OpenCV 引擎比对: screen=%s, icon=%s", screen_img_path, icon_img_path)
            return self._verify_with_opencv_path(screen_img_path, icon_img_path, threshold)

        logger.info("[比对] 使用 DINOv2(%s) 引擎比对: screen=%s, icon=%s", active_model['name'], screen_img_path, icon_img_path)

        try:
            img_screen = cv2.imread(screen_img_path)
            img_icon = cv2.imread(icon_img_path)
            if img_screen is None:
                return {
                    "success": False,
                    "message": f"屏幕截图读取失败: {screen_img_path}",
                    "score": 0,
                    "matched": False,
                    "engine": "dinov2",
                    "model_name": active_model["name"],
                }
            if img_icon is None:
                logger.error("[比对] 图标读取失败: %s", icon_img_path)
                return {
                    "success": False,
                    "message": f"图标读取失败: {icon_img_path}",
                    "score": 0,
                    "matched": False,
                    "engine": "dinov2",
                    "model_name": active_model["name"],
                }
            result = self._verify_with_dinov2_arrays(img_screen, img_icon, threshold)
            logger.info("[比对] DINOv2 比对完成: matched=%s, score=%.4f", result.get('matched'), result.get('score', 0.0))
            return result
        except Exception as exc:
            logger.error("[比对] DINOv2 验证异常: %s", exc, exc_info=True)
            return {
                "success": False,
                "message": f"DINOv2 验证失败: {str(exc)}",
                "score": 0,
                "matched": False,
                "engine": "dinov2",
                "model_name": active_model["name"],
            }

    def verify_base64(self, screen_img_path: str, icon_img_base64: str, threshold: float = 0.9) -> dict[str, Any]:
        active_model = self.get_active_model()
        if active_model is None:
            logger.info("[比对] 使用 OpenCV 引擎比对 (base64): screen=%s", screen_img_path)
            return self._verify_with_opencv_base64(screen_img_path, icon_img_base64, threshold)

        logger.info("[比对] 使用 DINOv2(%s) 引擎比对 (base64): screen=%s", active_model['name'], screen_img_path)

        try:
            img_screen = cv2.imread(screen_img_path)
            img_icon = self._decode_base64_image(icon_img_base64)
            if img_screen is None:
                return {
                    "success": False,
                    "message": f"屏幕截图读取失败: {screen_img_path}",
                    "score": 0,
                    "matched": False,
                    "engine": "dinov2",
                    "model_name": active_model["name"],
                }
            if img_icon is None:
                logger.error("[比对] base64 校验图片解析失败")
                return {
                    "success": False,
                    "message": "base64 校验图片解析失败",
                    "score": 0,
                    "matched": False,
                    "engine": "dinov2",
                    "model_name": active_model["name"],
                }
            result = self._verify_with_dinov2_arrays(img_screen, img_icon, threshold)
            logger.info("[比对] DINOv2(base64) 比对完成: matched=%s, score=%.4f", result.get('matched'), result.get('score', 0.0))
            return result
        except Exception as exc:
            logger.error("[比对] DINOv2(base64) 验证异常: %s", exc, exc_info=True)
            return {
                "success": False,
                "message": f"DINOv2 验证失败: {str(exc)}",
                "score": 0,
                "matched": False,
                "engine": "dinov2",
                "model_name": active_model["name"],
            }


image_compare_service = ImageCompareService()


def verify_image_match(screen_img_path: str, icon_img_path: str, threshold: float = 0.9) -> dict[str, Any]:
    """根据当前图片模型选择结果执行校验。"""
    return image_compare_service.verify(screen_img_path, icon_img_path, threshold)


def verify_image_base64_match(screen_img_path: str, icon_img_base64: str, threshold: float = 0.9) -> dict[str, Any]:
    """根据当前图片模型选择结果执行 base64 校验。"""
    return image_compare_service.verify_base64(screen_img_path, icon_img_base64, threshold)