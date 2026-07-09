"""按键监听纠正规则的方案（scheme）管理。

历史上 ``monitor_key_mappings.json`` 是一份扁平的 ``{source: target}``
字典，所有项目共享同一份纠错规则。改造后落地结构变成：

.. code-block:: json

    {
        "active_scheme": "默认",
        "schemes": {
            "默认": {"00FC": "SOURCE"},
            "ProjA": {"0233": "APPS"}
        }
    }

读取时若仍是扁平字典，会自动包装到 ``schemes["默认"]`` 下后续写回，
对老用户透明。
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List


DEFAULT_SCHEME_NAME = "默认"
MAX_SCHEME_NAME_LENGTH = 30


class KeyMonitorMappingError(ValueError):
    """方案级映射操作的语义错误。"""


def _normalize_key(value: str) -> str:
    return (value or "").strip().upper()


def _normalize_scheme_name(value: str) -> str:
    name = (value or "").strip()
    if not name:
        raise KeyMonitorMappingError("方案名称不能为空")
    if len(name) > MAX_SCHEME_NAME_LENGTH:
        raise KeyMonitorMappingError(f"方案名称长度不能超过 {MAX_SCHEME_NAME_LENGTH} 个字符")
    if re.search(r"[\\/:*?\"<>|]", name):
        raise KeyMonitorMappingError("方案名称不能包含 \\ / : * ? \" < > |")
    return name


def _normalize_mapping(raw: Any) -> Dict[str, str]:
    """把任意输入的 ``{source: target}`` 归一化成大写键值对。"""
    if not isinstance(raw, dict):
        return {}

    normalized: Dict[str, str] = {}
    for source, target in raw.items():
        if not isinstance(source, str) or not isinstance(target, str):
            continue
        source_key = _normalize_key(source)
        target_key = _normalize_key(target)
        if source_key and target_key:
            normalized[source_key] = target_key
    return normalized


class KeyMonitorMappingService:
    """方案化的纠错规则读写。

    - 所有写入都会立即持久化。
    - 内存里维护一份"当前激活方案的扁平视图"，供 ``main.py`` 中
      ``resolve_monitored_key`` / ``get_monitor_valid_targets`` 等热路径
      直接使用，避免频繁读盘。
    """

    def __init__(self, storage_path: Path):
        self._storage_path = Path(storage_path)
        self._lock = Lock()
        self._config: Dict[str, Any] = self._load()

    # ───────────────────── 持久化 ─────────────────────

    @property
    def storage_path(self) -> Path:
        return self._storage_path

    def reload(self) -> None:
        with self._lock:
            self._config = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self._storage_path.exists():
            return self._build_empty_config()

        try:
            data = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._build_empty_config()

        return self._normalize_config(data)

    def _save_unlocked(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        serializable = {
            "active_scheme": self._config["active_scheme"],
            "schemes": {
                name: dict(sorted(mapping.items()))
                for name, mapping in sorted(self._config["schemes"].items())
            },
        }
        self._storage_path.write_text(
            json.dumps(serializable, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _normalize_config(self, data: Any) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return self._build_empty_config()

        # 旧扁平格式 {KEY: KEY} → 包装到默认方案，迁移落盘
        if "schemes" not in data:
            legacy_mapping = _normalize_mapping(data)
            return {
                "active_scheme": DEFAULT_SCHEME_NAME,
                "schemes": {DEFAULT_SCHEME_NAME: legacy_mapping},
            }

        raw_schemes = data.get("schemes")
        if not isinstance(raw_schemes, dict):
            return self._build_empty_config()

        schemes: Dict[str, Dict[str, str]] = {}
        for name, raw_mapping in raw_schemes.items():
            if not isinstance(name, str) or not name.strip():
                continue
            schemes[name.strip()] = _normalize_mapping(raw_mapping)

        if not schemes:
            schemes[DEFAULT_SCHEME_NAME] = {}

        active = data.get("active_scheme")
        if not isinstance(active, str) or active not in schemes:
            active = DEFAULT_SCHEME_NAME if DEFAULT_SCHEME_NAME in schemes else next(iter(schemes))

        return {"active_scheme": active, "schemes": schemes}

    @staticmethod
    def _build_empty_config() -> Dict[str, Any]:
        return {
            "active_scheme": DEFAULT_SCHEME_NAME,
            "schemes": {DEFAULT_SCHEME_NAME: {}},
        }

    # ───────────────────── 查询 ─────────────────────

    def list_schemes(self) -> Dict[str, Any]:
        with self._lock:
            active = self._config["active_scheme"]
            schemes_view = [
                {
                    "name": name,
                    "is_active": name == active,
                    "mapping_count": len(mapping),
                }
                for name, mapping in sorted(self._config["schemes"].items())
            ]
        return {
            "active_scheme": active,
            "schemes": schemes_view,
        }

    def get_active_scheme_name(self) -> str:
        with self._lock:
            return self._config["active_scheme"]

    def get_active_mapping(self) -> Dict[str, str]:
        with self._lock:
            active = self._config["active_scheme"]
            return dict(self._config["schemes"].get(active, {}))

    def get_scheme_mapping(self, scheme_name: str) -> Dict[str, str]:
        name = _normalize_scheme_name(scheme_name)
        with self._lock:
            self._require_scheme(name)
            return dict(self._config["schemes"][name])

    # ───────────────────── 方案管理 ─────────────────────

    def create_scheme(self, scheme_name: str) -> Dict[str, str]:
        name = _normalize_scheme_name(scheme_name)
        with self._lock:
            if name in self._config["schemes"]:
                raise KeyMonitorMappingError(f"方案 '{name}' 已存在")
            self._config["schemes"][name] = {}
            self._save_unlocked()
        return self.list_schemes()

    def duplicate_scheme(self, scheme_name: str, new_name: str) -> Dict[str, Any]:
        source = _normalize_scheme_name(scheme_name)
        target = _normalize_scheme_name(new_name)
        with self._lock:
            self._require_scheme(source)
            if target in self._config["schemes"]:
                raise KeyMonitorMappingError(f"方案 '{target}' 已存在")
            self._config["schemes"][target] = copy.deepcopy(self._config["schemes"][source])
            self._save_unlocked()
        return self.list_schemes()

    def rename_scheme(self, scheme_name: str, new_name: str) -> Dict[str, Any]:
        source = _normalize_scheme_name(scheme_name)
        target = _normalize_scheme_name(new_name)
        if source == target:
            return self.list_schemes()

        with self._lock:
            self._require_scheme(source)
            if target in self._config["schemes"]:
                raise KeyMonitorMappingError(f"方案 '{target}' 已存在")
            self._config["schemes"][target] = self._config["schemes"].pop(source)
            if self._config["active_scheme"] == source:
                self._config["active_scheme"] = target
            self._save_unlocked()
        return self.list_schemes()

    def delete_scheme(self, scheme_name: str) -> Dict[str, Any]:
        name = _normalize_scheme_name(scheme_name)
        with self._lock:
            self._require_scheme(name)
            if len(self._config["schemes"]) <= 1:
                raise KeyMonitorMappingError("至少需要保留一个方案")

            del self._config["schemes"][name]
            if self._config["active_scheme"] == name:
                self._config["active_scheme"] = next(iter(self._config["schemes"]))
            self._save_unlocked()
        return self.list_schemes()

    def activate_scheme(self, scheme_name: str) -> Dict[str, Any]:
        name = _normalize_scheme_name(scheme_name)
        with self._lock:
            self._require_scheme(name)
            self._config["active_scheme"] = name
            self._save_unlocked()
        return self.list_schemes()

    # ───────────────────── 规则读写（针对当前激活方案） ─────────────────────

    def upsert_mapping(self, source_key: str, target_key: str) -> Dict[str, str]:
        source = _normalize_key(source_key)
        target = _normalize_key(target_key)
        if not source:
            raise KeyMonitorMappingError("错误指令不能为空")
        if not target:
            raise KeyMonitorMappingError("正确指令不能为空")

        with self._lock:
            active = self._config["active_scheme"]
            mapping = self._config["schemes"].setdefault(active, {})
            mapping[source] = target
            self._save_unlocked()
            return dict(mapping)

    def delete_mapping(self, source_key: str) -> Dict[str, str]:
        source = _normalize_key(source_key)
        if not source:
            raise KeyMonitorMappingError("错误指令不能为空")

        with self._lock:
            active = self._config["active_scheme"]
            mapping = self._config["schemes"].setdefault(active, {})
            removed = mapping.pop(source, None) is not None
            if removed:
                self._save_unlocked()
            return dict(mapping)

    # ───────────────────── 内部 ─────────────────────

    def _require_scheme(self, scheme_name: str) -> None:
        if scheme_name not in self._config["schemes"]:
            raise KeyMonitorMappingError(f"方案 '{scheme_name}' 不存在")

    # ───────────────────── 辅助：所有目标 ─────────────────────

    def all_known_targets(self) -> List[str]:
        """返回**所有**方案中作为 target 出现过的按键集合，供 valid_targets 合并使用。"""
        targets: set[str] = set()
        with self._lock:
            for mapping in self._config["schemes"].values():
                targets.update(mapping.values())
        return sorted(targets)

    # ───────────────────── 导入 / 导出 ─────────────────────

    EXPORT_KIND = "checkpilot.key-monitor.scheme"
    EXPORT_SCHEMA_VERSION = 1

    def _build_export_payload(self, schemes_to_export: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
        from datetime import datetime, timezone

        return {
            "schema_version": self.EXPORT_SCHEMA_VERSION,
            "kind": self.EXPORT_KIND,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "schemes": {
                name: dict(sorted(mapping.items()))
                for name, mapping in sorted(schemes_to_export.items())
            },
        }

    def export_scheme(self, scheme_name: str) -> Dict[str, Any]:
        """导出单个方案为可序列化的 dict，前端可直接转 JSON 文件给用户下载。"""
        name = _normalize_scheme_name(scheme_name)
        with self._lock:
            self._require_scheme(name)
            mapping = dict(self._config["schemes"][name])
        return self._build_export_payload({name: mapping})

    def export_all_schemes(self) -> Dict[str, Any]:
        """导出全部方案。"""
        with self._lock:
            schemes = {
                name: dict(mapping)
                for name, mapping in self._config["schemes"].items()
            }
        return self._build_export_payload(schemes)

    @staticmethod
    def _parse_import_payload(payload: Any) -> Dict[str, Dict[str, str]]:
        """把导入 JSON 解析成 ``{name: mapping}``。

        兼容三种来源格式：

        1. **完整导出格式**：``{"kind": ..., "schemes": {name: {...}}}``
        2. **方案集合（无元信息）**：``{"schemes": {name: {...}}}``
        3. **单方案扁平格式**：直接是 ``{KEY: KEY}``——此时按"未命名方案"
           处理，调用方需要再传一个 ``scheme_name`` 进来。返回时用 ``""`` 作为 key。
        """
        if not isinstance(payload, dict):
            raise KeyMonitorMappingError("导入文件格式无效，应为 JSON 对象")

        # 完整导出格式
        kind = payload.get("kind")
        if isinstance(kind, str) and kind != KeyMonitorMappingService.EXPORT_KIND:
            raise KeyMonitorMappingError(
                f"导入文件类型不匹配：期望 {KeyMonitorMappingService.EXPORT_KIND}，实际 {kind}"
            )

        if "schemes" in payload and isinstance(payload["schemes"], dict):
            parsed: Dict[str, Dict[str, str]] = {}
            for raw_name, raw_mapping in payload["schemes"].items():
                if not isinstance(raw_name, str) or not raw_name.strip():
                    continue
                parsed[raw_name.strip()] = _normalize_mapping(raw_mapping)
            if not parsed:
                raise KeyMonitorMappingError("导入文件中未找到任何方案")
            return parsed

        # 看起来像扁平方案：{KEY: KEY}
        flat = _normalize_mapping(payload)
        if not flat:
            raise KeyMonitorMappingError("导入文件中未找到任何规则")
        return {"": flat}

    def _resolve_unique_name(self, base: str) -> str:
        """生成一个不与现有方案重名的新名字，例如 ``ProjA`` → ``ProjA (导入1)``。"""
        if base not in self._config["schemes"]:
            return base
        index = 1
        while True:
            candidate = f"{base} (导入{index})"
            if len(candidate) > MAX_SCHEME_NAME_LENGTH:
                # 防止超长：截取 base
                base_max_len = MAX_SCHEME_NAME_LENGTH - len(f" (导入{index})")
                candidate = f"{base[:max(1, base_max_len)]} (导入{index})"
            if candidate not in self._config["schemes"]:
                return candidate
            index += 1

    def import_schemes(
        self,
        payload: Any,
        *,
        conflict: str = "rename",
        scheme_name_override: str | None = None,
    ) -> Dict[str, Any]:
        """导入一个或多个方案。

        - ``conflict='rename'``: 重名时用 ``ProjA (导入1)`` 形式自动改名（默认）
        - ``conflict='overwrite'``: 重名时直接覆盖原方案
        - ``conflict='skip'``: 重名时跳过该方案
        - ``scheme_name_override``: 当导入文件是"单方案扁平格式"时，必须传入此参数指定方案名

        返回 ``{imported: [...], skipped: [...], renamed: [...], schemes_view, active_scheme}``。
        """
        if conflict not in {"rename", "overwrite", "skip"}:
            raise KeyMonitorMappingError(f"未知的冲突处理策略: {conflict}")

        parsed = self._parse_import_payload(payload)

        # 单方案扁平格式必须显式给名字
        if "" in parsed:
            if not scheme_name_override:
                raise KeyMonitorMappingError("导入扁平格式时必须提供方案名称")
            mapping = parsed.pop("")
            parsed[_normalize_scheme_name(scheme_name_override)] = mapping
        else:
            # 即使是完整格式，也允许调用方临时改名（仅当只有一个方案时）
            if scheme_name_override and len(parsed) == 1:
                old_name = next(iter(parsed))
                parsed = {_normalize_scheme_name(scheme_name_override): parsed[old_name]}

        for name in list(parsed.keys()):
            # 校验所有名字都合法
            try:
                _normalize_scheme_name(name)
            except KeyMonitorMappingError as exc:
                raise KeyMonitorMappingError(f"方案 '{name}' 名称不合法: {exc}") from exc

        imported: List[str] = []
        skipped: List[str] = []
        renamed: List[Dict[str, str]] = []

        with self._lock:
            for name, mapping in parsed.items():
                exists = name in self._config["schemes"]
                if exists and conflict == "skip":
                    skipped.append(name)
                    continue
                if exists and conflict == "rename":
                    new_name = self._resolve_unique_name(name)
                    self._config["schemes"][new_name] = mapping
                    renamed.append({"original": name, "saved_as": new_name})
                    imported.append(new_name)
                    continue
                # overwrite 或 不存在
                self._config["schemes"][name] = mapping
                imported.append(name)

            if imported or renamed:
                self._save_unlocked()

            schemes_view = [
                {
                    "name": n,
                    "is_active": n == self._config["active_scheme"],
                    "mapping_count": len(m),
                }
                for n, m in sorted(self._config["schemes"].items())
            ]
            active = self._config["active_scheme"]

        return {
            "imported": imported,
            "renamed": renamed,
            "skipped": skipped,
            "schemes": schemes_view,
            "active_scheme": active,
        }
