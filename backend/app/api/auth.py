"""Remote platform auth proxy routes."""
import base64
import binascii
import json
import logging
from datetime import datetime, timezone
from typing import Any
from urllib import error, parse, request

logger = logging.getLogger(__name__)

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..runtime import clear_platform_auth, get_platform_auth, set_platform_auth

router = APIRouter(prefix="/api/platform-auth", tags=["platform-auth"])

TMS_LOGIN_URL = "https://tms.zeasn.com/api/auth/login"
TMS_PROJECTS_URL = "https://tms.zeasn.com/api/projects"
TMS_MODULE_TREE_URL = "https://tms.zeasn.com/api/modules/tree"
TMS_TESTCASES_URL = "https://tms.zeasn.com/api/testcases"
TMS_LOGIN_TIMEOUT = 15
# 上游脚本鉴权 Key：所有发往 tms.zeasn.com 的请求都需要带这个 header
TMS_SCRIPT_API_KEY = "tms-script-api-key-2026"
TOKEN_KEY_NAMES = {
    "token",
    "accesstoken",
    "idtoken",
    "authtoken",
    "authorization",
    "bearertoken",
    "jwt",
}


def _log_dict_keys(data: Any, prefix: str = "", depth: int = 0, max_depth: int = 3) -> None:
    """递归打印字典结构的key，用于调试上游响应格式。"""
    if depth > max_depth:
        return
    indent = "  " * depth
    if isinstance(data, dict):
        for key, value in data.items():
            value_type = type(value).__name__
            if isinstance(value, dict):
                logger.debug(f"[{prefix}] {indent}{key}: dict({len(value)} keys)")
                _log_dict_keys(value, prefix, depth + 1, max_depth)
            elif isinstance(value, list):
                logger.debug(f"[{prefix}] {indent}{key}: list({len(value)} items)")
                if value and depth < max_depth:
                    _log_dict_keys(value[0], prefix, depth + 1, max_depth)
            else:
                # 值脱敏：字符串只显示前50字符
                if isinstance(value, str) and len(value) > 50:
                    logger.debug(f"[{prefix}] {indent}{key}: str({len(value)} chars) = {value[:50]}...")
                else:
                    logger.debug(f"[{prefix}] {indent}{key}: {value_type} = {value}")
    elif isinstance(data, list) and data:
        logger.debug(f"[{prefix}] {indent}[0]:")
        _log_dict_keys(data[0], prefix, depth + 1, max_depth)


class TmsLoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


def _normalize_token_key(value: str) -> str:
    return str(value or "").strip().lower().replace("_", "").replace("-", "")


def _clean_token_value(value: Any) -> str:
    token = str(value or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def _parse_upstream_payload(raw_text: str) -> dict | str:
    content = str(raw_text or "").strip()
    if not content:
        return {}

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return content


def extract_platform_token(payload: Any) -> str:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if _normalize_token_key(key) in TOKEN_KEY_NAMES:
                token = _clean_token_value(value)
                if token:
                    return token

        for value in payload.values():
            token = extract_platform_token(value)
            if token:
                return token

    if isinstance(payload, list):
        for item in payload:
            token = extract_platform_token(item)
            if token:
                return token

    return ""


def _decode_jwt_payload(token: str) -> dict[str, Any] | None:
    parts = str(token or "").split(".")
    if len(parts) != 3:
        return None

    payload_segment = parts[1]
    payload_segment += "=" * (-len(payload_segment) % 4)

    try:
        decoded_payload = base64.urlsafe_b64decode(payload_segment.encode("ascii"))
        payload = json.loads(decoded_payload.decode("utf-8"))
    except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return None

    return payload if isinstance(payload, dict) else None


def _extract_token_expiration(token: str) -> datetime | None:
    payload = _decode_jwt_payload(token)
    if not payload:
        return None

    raw_expiration = payload.get("exp")
    if isinstance(raw_expiration, bool):
        return None

    try:
        expiration_seconds = float(raw_expiration)
    except (TypeError, ValueError):
        return None

    try:
        return datetime.fromtimestamp(expiration_seconds, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _get_valid_platform_auth() -> tuple[dict[str, Any], str]:
    platform_auth = get_platform_auth()
    logger.debug(f"[Platform Auth] 读取认证状态: keys={list(platform_auth.keys()) if platform_auth else '空'}")

    token = _clean_token_value(platform_auth.get("token", ""))
    if not token:
        logger.warning("[Platform Auth] 未找到有效的token，可能未登录或token已被清除")
        logger.debug(f"[Platform Auth] 原始认证数据: {str(platform_auth)[:300]}")
        return {}, ""

    logger.debug(f"[Platform Auth] Token长度: {len(token)}, username={platform_auth.get('username', '未知')}")

    expiration = _extract_token_expiration(token)
    if expiration is not None:
        now = datetime.now(timezone.utc)
        remaining = (expiration - now).total_seconds()
        if expiration <= now:
            logger.warning(f"[Platform Auth] Token已过期: 过期时间={expiration.isoformat()}, 已过期{abs(remaining):.0f}秒")
            clear_platform_auth()
            return {}, ""
        logger.debug(f"[Platform Auth] Token有效期剩余: {remaining:.0f}秒, 过期时间={expiration.isoformat()}")
    else:
        logger.debug("[Platform Auth] 无法解析JWT过期时间，跳过过期检查")

    return platform_auth, token


def get_saved_platform_token() -> str:
    _, token = _get_valid_platform_auth()
    return token


def get_tms_auth_headers(extra_headers: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        # 上游脚本鉴权 Key 必须随请求一同发送；不带这个 header 时上游会直接拒绝
        "X-API-Key": TMS_SCRIPT_API_KEY,
    }
    if extra_headers:
        headers.update(extra_headers)

    token = get_saved_platform_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
        logger.debug(f"[TMS Auth] 构建请求头: token长度={len(token)}, X-API-Key已设置")
    else:
        logger.warning("[TMS Auth] 构建请求头: 无有效token，请求可能被上游拒绝")

    return headers


def _build_upstream_error_response(upstream_status: int, detail: str, upstream_payload: dict | str):
    return JSONResponse(
        status_code=upstream_status,
        content={
            "status": "error",
            "upstream_status": upstream_status,
            "detail": detail,
            "data": upstream_payload,
        },
    )


def _require_saved_platform_token() -> str:
    token = get_saved_platform_token()
    if token:
        logger.debug(f"[TMS Auth] Token校验通过: 长度={len(token)}")
        return token

    logger.warning("[TMS Auth] Token校验失败: 未找到有效token，抛出401")
    logger.warning(f"[TMS Auth] 当前认证状态: {get_platform_auth()}")
    raise HTTPException(status_code=401, detail="请先在首页完成平台登录，再访问线上用例库")


def _build_tms_get_url(base_url: str, query_params: dict[str, Any] | None = None) -> str:
    if not query_params:
        return base_url

    filtered_params = {
        key: value
        for key, value in query_params.items()
        if value is not None and str(value).strip() != ""
    }
    if not filtered_params:
        return base_url

    return f"{base_url}?{parse.urlencode(filtered_params, doseq=True)}"


def fetch_tms_get(base_url: str, query_params: dict[str, Any] | None = None) -> tuple[int, dict | str]:
    logger.info(f"[TMS] ========== TMS GET 请求开始 ==========")
    logger.info(f"[TMS] 目标URL: {base_url}")
    logger.info(f"[TMS] 查询参数: {query_params}")

    token = _require_saved_platform_token()
    logger.info(f"[TMS] Token校验通过: 长度={len(token)}")

    request_url = _build_tms_get_url(base_url, query_params)
    logger.info(f"[TMS] 完整请求URL: {request_url}")

    headers = get_tms_auth_headers()
    # 脱敏显示Authorization头
    auth_header = headers.get("Authorization", "")
    if auth_header:
        logger.debug(f"[TMS] Authorization: Bearer {token[:15]}...{token[-8:]}")
    logger.debug(f"[TMS] 请求头: {headers}")

    remote_request = request.Request(
        request_url,
        headers=headers,
        method="GET",
    )

    try:
        with request.urlopen(remote_request, timeout=TMS_LOGIN_TIMEOUT) as response:
            body = response.read().decode("utf-8", errors="replace")
            logger.info(f"[TMS] 响应成功: status={response.getcode()}, body_length={len(body)}")
            logger.debug(f"[TMS] 响应内容前500字符: {body[:500]}")
            logger.info(f"[TMS] ========== TMS GET 请求结束(成功) ==========")
            return response.getcode(), _parse_upstream_payload(body)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logger.error(f"[TMS] HTTP错误: status={exc.code}, url={request_url}")
        logger.error(f"[TMS] 错误响应头: {dict(exc.headers)}")
        logger.error(f"[TMS] 错误响应内容: {body[:1000]}")
        logger.error(f"[TMS] ========== TMS GET 请求结束(HTTP错误) ==========")
        return exc.code, _parse_upstream_payload(body)
    except error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        logger.error(f"[TMS] 连接失败: reason={reason}, url={request_url}")
        logger.error(f"[TMS] 异常类型: {type(exc).__name__}")
        if hasattr(reason, 'errno'):
            logger.error(f"[TMS] 错误码: {reason.errno}")
        if hasattr(reason, 'strerror'):
            logger.error(f"[TMS] 错误描述: {reason.strerror}")
        logger.error(f"[TMS] ========== TMS GET 请求结束(连接失败) ==========")
        raise HTTPException(status_code=502, detail=f"连接线上用例接口失败: {reason}") from exc
    except Exception as exc:
        logger.error(f"[TMS] 未预期异常: {type(exc).__name__}: {exc}", exc_info=True)
        logger.error(f"[TMS] ========== TMS GET 请求结束(异常) ==========")
        raise HTTPException(status_code=500, detail=f"TMS请求异常: {exc}") from exc


def _build_platform_auth_state(username: str, token: str, upstream_status: int) -> dict[str, Any]:
    return {
        "username": username,
        "token": token,
        "login_url": TMS_LOGIN_URL,
        "upstream_status": upstream_status,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }


def build_platform_auth_status() -> dict[str, Any]:
    platform_auth, token = _get_valid_platform_auth()

    return {
        "status": "success",
        "authenticated": bool(token),
        "username": str(platform_auth.get("username", "")).strip() if token else "",
        "saved_at": str(platform_auth.get("saved_at", "")).strip() if token else "",
    }


def extract_project_options(payload: Any) -> list[dict[str, Any]]:
    data = payload.get("data") if isinstance(payload, dict) else None

    # 兼容两种上游结构：
    # - 旧 /teams/{id}/projects: data 直接是 list
    # - 新 /projects: data 是 {"records": [...], "total": N}
    if isinstance(data, dict):
        records = data.get("records")
        if isinstance(records, list):
            data = records
        else:
            data = []
    if not isinstance(data, list):
        return []

    projects: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue

        project_id = item.get("id")
        project_name = str(item.get("name", "")).strip()
        if project_id in (None, "") or not project_name:
            continue

        projects.append({
            "id": project_id,
            "name": project_name,
        })

    return projects


def extract_module_options(payload: Any) -> list[dict[str, str]]:
    modules: list[dict[str, str]] = []
    seen_values: set[str] = set()
    source = payload.get("data") if isinstance(payload, dict) else payload

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            name = str(node.get("name", "")).strip()
            path = str(node.get("path", "")).strip()
            value = path or name
            if name and value and value not in seen_values:
                seen_values.add(value)
                modules.append({
                    "name": name,
                    "value": value,
                })

            for value in node.values():
                if isinstance(value, (dict, list)):
                    visit(value)
            return

        if isinstance(node, list):
            for item in node:
                visit(item)

    visit(source)
    return modules


def extract_testcase_items(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    containers = [payload.get("data"), payload]
    for container in containers:
        if isinstance(container, list):
            return [item for item in container if isinstance(item, dict)]

        if not isinstance(container, dict):
            continue

        for key in ("list", "items", "records", "rows", "data"):
            value = container.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    return []


def extract_case_number(value: Any) -> str:
    if isinstance(value, dict):
        for key, item in value.items():
            if _normalize_token_key(key) == "casenumber":
                case_number = str(item or "").strip()
                if case_number:
                    return case_number

        for item in value.values():
            case_number = extract_case_number(item)
            if case_number:
                return case_number

    if isinstance(value, list):
        for item in value:
            case_number = extract_case_number(item)
            if case_number:
                return case_number

    return ""


def extract_testcase_case_numbers(payload: Any) -> list[str]:
    case_numbers: list[str] = []
    seen_case_numbers: set[str] = set()

    for item in extract_testcase_items(payload):
        case_number = extract_case_number(item)
        if not case_number or case_number in seen_case_numbers:
            continue

        seen_case_numbers.add(case_number)
        case_numbers.append(case_number)

    return case_numbers


def _coerce_text(value: Any) -> str:
    if value in (None, "", []):
        return ""
    if isinstance(value, (str, int, float)):
        return str(value).strip()
    return ""


def _parse_testcase_steps(value: Any) -> list[dict[str, str]]:
    """把 testcase 的 steps 字段解析成 ``[{step, expected}, ...]``。

    上游接口里 steps 通常是 JSON 字符串：
    ``"[{\\"step\\": \\"按Mute键\\", \\"expected\\": \\"可正常响应Mute按键\\"}]"``，
    所以需要先 ``json.loads`` 一次再按列表解析。也兼容已经是数组的情况。
    """
    if not value:
        return []

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError):
            return [{"step": text, "expected": ""}]
        return _parse_testcase_steps(parsed)

    if isinstance(value, list):
        steps: list[dict[str, str]] = []
        for item in value:
            if isinstance(item, dict):
                step_text = _coerce_text(item.get("step"))
                expected_text = _coerce_text(item.get("expected"))
                if step_text or expected_text:
                    steps.append({"step": step_text, "expected": expected_text})
            else:
                step_text = _coerce_text(item)
                if step_text:
                    steps.append({"step": step_text, "expected": ""})
        return steps

    if isinstance(value, dict):
        step_text = _coerce_text(value.get("step"))
        expected_text = _coerce_text(value.get("expected"))
        if step_text or expected_text:
            return [{"step": step_text, "expected": expected_text}]
        return []

    return []


def extract_testcase_details(payload: Any) -> list[dict[str, Any]]:
    """返回 ``[{case_number, precondition, steps, module}, ...]``，按出现顺序去重。"""
    details: list[dict[str, Any]] = []
    seen_case_numbers: set[str] = set()

    for item in extract_testcase_items(payload):
        case_number = extract_case_number(item)
        if not case_number or case_number in seen_case_numbers:
            continue

        seen_case_numbers.add(case_number)
        details.append({
            "case_number": case_number,
            "precondition": _coerce_text(item.get("precondition")),
            "steps": _parse_testcase_steps(item.get("steps")),
            "module": _extract_module_label(item),
        })

    return details


def extract_testcase_summaries(payload: Any) -> list[dict[str, Any]]:
    """搜索专用的精简结构：``[{case_number, module}, ...]``。

    省掉 precondition / steps，可显著缩小搜索阶段的传输体积。
    选中后由前端按需补拉完整 detail。
    """
    summaries: list[dict[str, Any]] = []
    seen_case_numbers: set[str] = set()

    for item in extract_testcase_items(payload):
        case_number = extract_case_number(item)
        if not case_number or case_number in seen_case_numbers:
            continue

        seen_case_numbers.add(case_number)
        summaries.append({
            "case_number": case_number,
            "module": _extract_module_label(item),
        })

    return summaries


def _extract_module_label(item: Any) -> str:
    """从用例项中提取模块名/路径，兼容多种字段名。"""
    if not isinstance(item, dict):
        return ""

    # 常见命名：module / module_name / moduleName / module_path / modulePath
    candidate_keys = (
        "module_name",
        "moduleName",
        "module_path",
        "modulePath",
        "module",
    )
    for key in candidate_keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            for sub_key in ("name", "label", "title", "path"):
                sub_value = value.get(sub_key)
                if isinstance(sub_value, str) and sub_value.strip():
                    return sub_value.strip()

    return ""


def extract_total_count(payload: Any, fallback_count: int) -> int:
    if not isinstance(payload, dict):
        return fallback_count

    containers = [payload.get("data"), payload]
    for container in containers:
        if not isinstance(container, dict):
            continue

        for key in ("total", "count", "total_count", "recordCount"):
            value = container.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)

    return fallback_count


def post_tms_login(username: str, password: str) -> tuple[int, dict | str]:
    payload = json.dumps({
        "username": username,
        "password": password,
    }, ensure_ascii=False).encode("utf-8")
    remote_request = request.Request(
        TMS_LOGIN_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-Key": TMS_SCRIPT_API_KEY,
        },
        method="POST",
    )

    logger.info(f"[TMS Login] 发起上游登录请求: url={TMS_LOGIN_URL}, username={username}, timeout={TMS_LOGIN_TIMEOUT}s")
    logger.debug(f"[TMS Login] 请求头: Content-Type=application/json, X-API-Key={TMS_SCRIPT_API_KEY[:8]}...")

    try:
        with request.urlopen(remote_request, timeout=TMS_LOGIN_TIMEOUT) as response:
            body = response.read().decode("utf-8", errors="replace")
            logger.info(f"[TMS Login] 上游响应成功: status={response.getcode()}, body_length={len(body)}")
            logger.debug(f"[TMS Login] 上游响应内容: {body[:1000]}")
            return response.getcode(), _parse_upstream_payload(body)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logger.error(f"[TMS Login] 上游HTTP错误: status={exc.code}, url={TMS_LOGIN_URL}")
        logger.error(f"[TMS Login] 错误响应头: {dict(exc.headers)}")
        logger.error(f"[TMS Login] 错误响应内容: {body[:1000]}")
        return exc.code, _parse_upstream_payload(body)
    except error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        logger.error(f"[TMS Login] 上游连接失败: reason={reason}, url={TMS_LOGIN_URL}")
        logger.error(f"[TMS Login] 异常类型: {type(exc).__name__}, 原始异常: {type(reason).__name__ if reason else 'N/A'}")
        raise HTTPException(status_code=502, detail=f"连接线上登录接口失败: {reason}") from exc
    except Exception as exc:
        logger.error(f"[TMS Login] 未预期异常: {type(exc).__name__}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"登录请求异常: {exc}") from exc


@router.get("/status")
def get_remote_platform_auth_status():
    return build_platform_auth_status()


@router.post("/logout")
def logout_remote_platform():
    clear_platform_auth()
    return {
        "status": "success",
        "authenticated": False,
        "username": "",
        "saved_at": "",
    }


@router.get("/projects")
def list_remote_projects():
    logger.info("[TMS Projects] 开始获取项目列表")
    upstream_status, upstream_payload = fetch_tms_get(TMS_PROJECTS_URL)

    if not 200 <= upstream_status < 300:
        logger.error(f"[TMS Projects] 获取项目失败: 状态码={upstream_status}")
        return _build_upstream_error_response(upstream_status, "加载线上用例库失败", upstream_payload)

    projects = extract_project_options(upstream_payload)
    logger.info(f"[TMS Projects] 成功获取项目: 数量={len(projects)}")
    logger.debug(f"[TMS Projects] 项目列表: {[p.get('name') for p in projects[:5]]}")

    return {
        "status": "success",
        "projects": projects,
    }


@router.get("/modules")
def list_remote_modules(project_ids: str = Query(..., min_length=1)):
    logger.info(f"[TMS Modules] 开始获取模块列表: project_ids={project_ids}")
    upstream_status, upstream_payload = fetch_tms_get(
        TMS_MODULE_TREE_URL,
        query_params={"project_ids": project_ids},
    )

    if not 200 <= upstream_status < 300:
        logger.error(f"[TMS Modules] 获取模块失败: 状态码={upstream_status}")
        return _build_upstream_error_response(upstream_status, "加载线上模块列表失败", upstream_payload)

    modules = extract_module_options(upstream_payload)
    logger.info(f"[TMS Modules] 成功获取模块: 数量={len(modules)}")
    logger.debug(f"[TMS Modules] 模块列表: {[m.get('name') for m in modules[:10]]}")

    return {
        "status": "success",
        "modules": modules,
    }


@router.get("/testcases")
def list_remote_testcases(
    project_ids: str = Query(..., min_length=1),
    module: str = Query(..., min_length=1),
    size: int = Query(20, ge=1, le=100),
    page: int = Query(1, ge=1),
    fields: str = Query("full"),
):
    logger.info(f"[TMS Testcases] 开始获取用例列表: project_ids={project_ids}, module={module}, size={size}, page={page}, fields={fields}")

    # 单测会绕过 FastAPI 的 Query 解析直接调用，保留 Query 默认值时需要手动归一化
    try:
        page_value = int(page)
    except (TypeError, ValueError):
        page_value = 1
    if page_value < 1:
        page_value = 1

    upstream_status, upstream_payload = fetch_tms_get(
        TMS_TESTCASES_URL,
        query_params={
            "page": page_value,
            "size": size,
            "project_ids": project_ids,
            "module": module,
        },
    )

    if not 200 <= upstream_status < 300:
        logger.error(f"[TMS Testcases] 获取用例失败: 状态码={upstream_status}")
        logger.debug(f"[TMS Testcases] 失败响应: {str(upstream_payload)[:500]}")
        return _build_upstream_error_response(upstream_status, "加载线上测试用例失败", upstream_payload)

    # summary 模式：仅返回 case_number + module，省掉 precondition + steps；
    # 用例搜索时跨页拉全集只需要这两个字段，可以显著缩小后端→前端的传输体积。
    if str(fields).strip().lower() == "summary":
        details = extract_testcase_summaries(upstream_payload)
    else:
        details = extract_testcase_details(upstream_payload)
    case_numbers = [item["case_number"] for item in details]

    logger.info(f"[TMS Testcases] 成功获取用例: 数量={len(case_numbers)}, 总数={extract_total_count(upstream_payload, len(case_numbers))}")
    logger.debug(f"[TMS Testcases] 用例编号列表: {case_numbers[:10]}{'...' if len(case_numbers) > 10 else ''}")

    return {
        "status": "success",
        "case_numbers": case_numbers,
        "testcases": details,
        "total": extract_total_count(upstream_payload, len(case_numbers)),
    }


@router.post("/login")
async def login_to_remote_platform(payload: TmsLoginRequest):
    logger.info(f"[TMS Login] ========== 登录流程开始 ==========")
    logger.info(f"[TMS Login] 用户名: {payload.username}")
    logger.info(f"[TMS Login] 密码长度: {len(payload.password)}")

    upstream_status, upstream_payload = post_tms_login(payload.username, payload.password)

    logger.info(f"[TMS Login] 上游返回状态码: {upstream_status}")
    logger.debug(f"[TMS Login] 上游返回内容类型: {type(upstream_payload).__name__}")
    if isinstance(upstream_payload, dict):
        logger.debug(f"[TMS Login] 上游返回顶层key: {list(upstream_payload.keys())}")

    if 200 <= upstream_status < 300:
        logger.info(f"[TMS Login] 上游响应成功，开始提取token...")
        token = extract_platform_token(upstream_payload)
        token_saved = bool(token)

        if token_saved:
            # 脱敏显示token：只显示前20字符和后10字符
            token_preview = f"{token[:20]}...{token[-10:]}" if len(token) > 30 else token[:20] + "..."
            logger.info(f"[TMS Login] Token提取成功: 长度={len(token)}, 预览={token_preview}")

            # 解析JWT过期时间
            expiration = _extract_token_expiration(token)
            if expiration:
                logger.info(f"[TMS Login] JWT过期时间: {expiration.isoformat()}")
            else:
                logger.warning(f"[TMS Login] 无法解析JWT过期时间，token可能不是标准JWT格式")

            auth_state = _build_platform_auth_state(payload.username, token, upstream_status)
            set_platform_auth(auth_state)
            logger.info(f"[TMS Login] Token已保存到运行时状态: saved_at={auth_state.get('saved_at')}")
        else:
            logger.warning(f"[TMS Login] 登录成功但未提取到token!")
            logger.warning(f"[TMS Login] 上游响应结构: {str(upstream_payload)[:500]}")
            # 递归打印所有key帮助调试
            if isinstance(upstream_payload, dict):
                _log_dict_keys(upstream_payload, prefix="上游响应")

        logger.info(f"[TMS Login] ========== 登录流程结束(成功) ==========")
        return {
            "status": "success",
            "upstream_status": upstream_status,
            "data": upstream_payload,
            "token_saved": token_saved,
            "saved_username": payload.username if token_saved else "",
        }

    logger.error(f"[TMS Login] ========== 登录流程结束(失败) ==========")
    logger.error(f"[TMS Login] 失败详情: status={upstream_status}, payload={str(upstream_payload)[:500]}")
    return _build_upstream_error_response(upstream_status, "线上登录接口返回错误", upstream_payload)