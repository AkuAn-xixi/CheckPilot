"""客制化配置 API — 支持多方案（scheme）管理"""
import copy
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List

from ..config import settings
from ..utils.adb_controller import KEYCODE_MAP

router = APIRouter(prefix="/api/customization", tags=["customization"])

DEFAULT_SCHEME_NAME = "默认"

DEFAULT_VALID_KEYS: List[str] = sorted([
    'OK', 'RIGHT', 'UP', 'LEFT', 'DOWN', 'SETTING', 'HOME', 'POWER', 'BACK',
    'SOURCE', 'MENU', 'CHUP', 'CHDOWN', 'DIGITAL', 'EXITMENU', 'DIGITAL0',
    'DIGITAL1', 'DIGITAL2', 'DIGITAL3', 'DIGITAL4', 'DIGITAL5', 'DIGITAL6',
    'DIGITAL7', 'DIGITAL8', 'DIGITAL9', 'LIBRARY', 'TV_AV', 'VOLUMEUP',
    'VOLUMEDOWN', 'NETFLIX', 'YOUTUBE', 'PRIME_VIDEO', 'ACTION3', 'APPS',
    'FILES', 'MUTE',
])


# ─── 请求体模型 ────────────────────────────────────────────────────────────────

class ValidKeysUpdateRequest(BaseModel):
    keys: List[str]


class KeyCodesUpdateRequest(BaseModel):
    key_codes: Dict[str, int]


class CreateSchemeRequest(BaseModel):
    name: str


class DuplicateSchemeRequest(BaseModel):
    new_name: str


# ─── 配置读写 ──────────────────────────────────────────────────────────────────

def _normalize_config(data: dict) -> dict:
    schemes = data.get("schemes")
    if not isinstance(schemes, dict):
        schemes = {}

    normalized_schemes = {
        name: scheme if isinstance(scheme, dict) else {}
        for name, scheme in schemes.items()
        if isinstance(name, str) and name.strip()
    }

    if DEFAULT_SCHEME_NAME not in normalized_schemes:
        normalized_schemes[DEFAULT_SCHEME_NAME] = {}

    active_scheme = data.get("active_scheme")
    if not isinstance(active_scheme, str) or active_scheme not in normalized_schemes:
        active_scheme = DEFAULT_SCHEME_NAME

    return {
        "active_scheme": active_scheme,
        "schemes": normalized_schemes,
    }

def _load_config() -> dict:
    path = settings.CUSTOMIZATION_FILE
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 迁移：旧的扁平格式 → 新的方案格式
            if "schemes" not in data:
                scheme: dict = {}
                if isinstance(data.get("valid_keys"), list):
                    scheme["valid_keys"] = data["valid_keys"]
                if isinstance(data.get("key_codes"), dict):
                    scheme["key_codes"] = data["key_codes"]
                return _normalize_config({
                    "active_scheme": DEFAULT_SCHEME_NAME,
                    "schemes": {DEFAULT_SCHEME_NAME: scheme},
                })
            return _normalize_config(data)
        except Exception:
            pass
    return _normalize_config({})


def _save_config(data: dict) -> None:
    path = settings.CUSTOMIZATION_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _require_scheme(config: dict, name: str) -> dict:
    scheme = config.get("schemes", {}).get(name)
    if scheme is None:
        raise HTTPException(status_code=404, detail=f"方案 '{name}' 不存在")
    return scheme


# ─── 方案管理 ──────────────────────────────────────────────────────────────────

@router.get("/schemes")
def list_schemes():
    """列出所有方案及当前激活方案名"""
    config = _load_config()
    active = config.get("active_scheme", DEFAULT_SCHEME_NAME)
    schemes = config.get("schemes", {})
    return {
        "active_scheme": active,
        "schemes": [
            {
                "name": name,
                "is_active": name == active,
                "valid_keys_count": len(s.get("valid_keys") or DEFAULT_VALID_KEYS),
                "key_codes_count": len(s.get("key_codes", {})),
            }
            for name, s in schemes.items()
        ],
    }


@router.post("/schemes")
def create_scheme(req: CreateSchemeRequest):
    """新建方案（空方案，使用默认按键与键值）"""
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="方案名称不能为空")
    config = _load_config()
    if name in config.get("schemes", {}):
        raise HTTPException(status_code=409, detail=f"方案 '{name}' 已存在")
    config.setdefault("schemes", {})[name] = {}
    if not config.get("active_scheme") or config["active_scheme"] not in config["schemes"]:
        config["active_scheme"] = name
    _save_config(config)
    return {"name": name, "active_scheme": config["active_scheme"]}


@router.delete("/schemes/{scheme_name}")
def delete_scheme(scheme_name: str):
    """删除方案（至少保留一个）"""
    config = _load_config()
    schemes = config.get("schemes", {})
    if scheme_name not in schemes:
        raise HTTPException(status_code=404, detail=f"方案 '{scheme_name}' 不存在")
    if len(schemes) <= 1:
        raise HTTPException(status_code=400, detail="至少需要保留一个方案")
    del schemes[scheme_name]
    if config.get("active_scheme") == scheme_name:
        config["active_scheme"] = next(iter(schemes))
    _save_config(config)
    return {"message": f"方案 '{scheme_name}' 已删除", "active_scheme": config["active_scheme"]}


@router.put("/schemes/{scheme_name}/activate")
def activate_scheme(scheme_name: str):
    """将指定方案设为激活方案（运行时读取该方案的配置）"""
    config = _load_config()
    _require_scheme(config, scheme_name)
    config["active_scheme"] = scheme_name
    _save_config(config)
    return {"active_scheme": scheme_name}


@router.post("/schemes/{scheme_name}/duplicate")
def duplicate_scheme(scheme_name: str, req: DuplicateSchemeRequest):
    """复制方案"""
    new_name = req.new_name.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="新方案名称不能为空")
    config = _load_config()
    source = _require_scheme(config, scheme_name)
    if new_name in config.get("schemes", {}):
        raise HTTPException(status_code=409, detail=f"方案 '{new_name}' 已存在")
    config["schemes"][new_name] = copy.deepcopy(source)
    _save_config(config)
    return {"name": new_name}


# ─── 合法按键名称 ──────────────────────────────────────────────────────────────

@router.get("/schemes/{scheme_name}/valid-keys")
def get_valid_keys(scheme_name: str):
    config = _load_config()
    scheme = _require_scheme(config, scheme_name)
    custom = scheme.get("valid_keys")
    if isinstance(custom, list) and custom:
        return {"keys": sorted(custom), "is_custom": True}
    return {"keys": DEFAULT_VALID_KEYS, "is_custom": False}


@router.put("/schemes/{scheme_name}/valid-keys")
def update_valid_keys(scheme_name: str, req: ValidKeysUpdateRequest):
    keys = sorted(set(k.strip().upper() for k in req.keys if k.strip()))
    if not keys:
        raise HTTPException(status_code=400, detail="按键列表不能为空")
    config = _load_config()
    _require_scheme(config, scheme_name)
    config["schemes"][scheme_name]["valid_keys"] = keys
    _save_config(config)
    return {"keys": keys}


@router.post("/schemes/{scheme_name}/valid-keys/reset")
def reset_valid_keys(scheme_name: str):
    config = _load_config()
    _require_scheme(config, scheme_name)
    config["schemes"][scheme_name].pop("valid_keys", None)
    _save_config(config)
    return {"keys": DEFAULT_VALID_KEYS}


# ─── 键值映射 ──────────────────────────────────────────────────────────────────

@router.get("/schemes/{scheme_name}/key-codes")
def get_key_codes(scheme_name: str):
    config = _load_config()
    scheme = _require_scheme(config, scheme_name)
    custom = {k.upper(): v for k, v in scheme.get("key_codes", {}).items()}
    merged = {**KEYCODE_MAP, **custom}
    return {
        "key_codes": dict(sorted(merged.items())),
        "custom_overrides": dict(sorted(custom.items())),
    }


@router.put("/schemes/{scheme_name}/key-codes")
def update_key_codes(scheme_name: str, req: KeyCodesUpdateRequest):
    validated: Dict[str, int] = {}
    for k, v in req.key_codes.items():
        key = k.strip().upper()
        if not key:
            raise HTTPException(status_code=400, detail="按键名称不能为空")
        if not isinstance(v, int) or v < 0:
            raise HTTPException(status_code=400, detail=f"'{key}' 的键值必须为非负整数")
        validated[key] = v
    config = _load_config()
    _require_scheme(config, scheme_name)
    config["schemes"][scheme_name]["key_codes"] = validated
    _save_config(config)
    merged = {**KEYCODE_MAP, **validated}
    return {
        "key_codes": dict(sorted(merged.items())),
        "custom_overrides": dict(sorted(validated.items())),
    }


@router.delete("/schemes/{scheme_name}/key-codes/{key_name}")
def delete_key_code(scheme_name: str, key_name: str):
    config = _load_config()
    _require_scheme(config, scheme_name)
    key = key_name.strip().upper()
    overrides = config["schemes"][scheme_name].get("key_codes", {})
    if key not in overrides:
        raise HTTPException(status_code=404, detail=f"'{key}' 不是自定义键值")
    del overrides[key]
    config["schemes"][scheme_name]["key_codes"] = overrides
    _save_config(config)
    merged = {**KEYCODE_MAP, **overrides}
    return {
        "key_codes": dict(sorted(merged.items())),
        "custom_overrides": dict(sorted(overrides.items())),
    }


@router.post("/schemes/{scheme_name}/key-codes/reset")
def reset_key_codes(scheme_name: str):
    config = _load_config()
    _require_scheme(config, scheme_name)
    config["schemes"][scheme_name].pop("key_codes", None)
    _save_config(config)
    return {
        "key_codes": dict(sorted(KEYCODE_MAP.items())),
        "custom_overrides": {},
    }


@router.delete("/key-codes/{key_name}")
async def delete_key_code_override(key_name: str):
    """删除单个自定义键值覆盖（还原为默认值）"""
    key = key_name.strip().upper()
    cfg = _load_config()
    custom = cfg.get("key_codes", {})
    custom.pop(key, None)
    cfg["key_codes"] = custom
    _save_config(cfg)
    merged = {**KEYCODE_MAP, **{k.upper(): v for k, v in custom.items()}}
    return {
        "key_codes": dict(sorted(merged.items())),
        "custom_overrides": dict(sorted({k.upper(): v for k, v in custom.items()}.items())),
    }


@router.post("/key-codes/reset")
async def reset_key_codes():
    """清除所有自定义键值覆盖，还原为全部默认值"""
    cfg = _load_config()
    cfg.pop("key_codes", None)
    _save_config(cfg)
    return {
        "key_codes": dict(sorted(KEYCODE_MAP.items())),
        "custom_overrides": {},
    }
