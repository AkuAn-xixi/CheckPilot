import asyncio
import base64
import io
import json
import unittest
from datetime import datetime, timezone
from unittest import mock
from urllib import parse
from urllib import error

from fastapi import HTTPException

from backend.app.api import auth


def make_jwt_with_exp(expiration_timestamp: float) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode("utf-8")).decode("ascii").rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"exp": expiration_timestamp}).encode("utf-8")).decode("ascii").rstrip("=")
    signature = "demo-signature"
    return f"{header}.{payload}.{signature}"


class FakeHTTPResponse:
    def __init__(self, status: int, payload):
        self._status = status
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def getcode(self):
        return self._status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class RemotePlatformAuthTests(unittest.TestCase):
    def test_post_tms_login_sends_expected_json_payload(self):
        captured = {}

        def fake_urlopen(remote_request, timeout):
            headers = {key.lower(): value for key, value in remote_request.header_items()}
            captured["url"] = remote_request.full_url
            captured["method"] = remote_request.get_method()
            captured["content_type"] = headers.get("content-type")
            captured["accept"] = headers.get("accept")
            captured["timeout"] = timeout
            captured["payload"] = json.loads(remote_request.data.decode("utf-8"))
            return FakeHTTPResponse(200, {"token": "demo-token"})

        with mock.patch("backend.app.api.auth.request.urlopen", side_effect=fake_urlopen):
            status, payload = auth.post_tms_login("Zephyr", "Whaletv123456")

        self.assertEqual(status, 200)
        self.assertEqual(payload, {"token": "demo-token"})
        self.assertEqual(captured["url"], auth.TMS_LOGIN_URL)
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["content_type"], "application/json")
        self.assertEqual(captured["accept"], "application/json")
        self.assertEqual(captured["timeout"], auth.TMS_LOGIN_TIMEOUT)
        self.assertEqual(captured["payload"], {
            "username": "Zephyr",
            "password": "Whaletv123456",
        })

    def test_post_tms_login_returns_upstream_http_error_payload(self):
        upstream_error = error.HTTPError(
            auth.TMS_LOGIN_URL,
            401,
            "Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b'{"message":"Invalid credentials"}'),
        )

        with mock.patch("backend.app.api.auth.request.urlopen", side_effect=upstream_error):
            status, payload = auth.post_tms_login("Zephyr", "wrong-pass")

        self.assertEqual(status, 401)
        self.assertEqual(payload, {"message": "Invalid credentials"})

    def test_post_tms_login_raises_http_exception_when_upstream_unreachable(self):
        with mock.patch(
            "backend.app.api.auth.request.urlopen",
            side_effect=error.URLError("offline"),
        ):
            with self.assertRaises(HTTPException) as context:
                auth.post_tms_login("Zephyr", "Whaletv123456")

        self.assertEqual(context.exception.status_code, 502)
        self.assertIn("连接线上登录接口失败", context.exception.detail)

    def test_extract_platform_token_supports_nested_payload(self):
        payload = {
            "code": 0,
            "data": {
                "user": {"name": "Zephyr"},
                "accessToken": "Bearer nested-demo-token",
            },
        }

        self.assertEqual(auth.extract_platform_token(payload), "nested-demo-token")

    def test_get_tms_auth_headers_uses_saved_token(self):
        with mock.patch("backend.app.api.auth.get_platform_auth", return_value={"token": "saved-demo-token"}):
            headers = auth.get_tms_auth_headers({"Content-Type": "application/json"})

        self.assertEqual(headers["Accept"], "application/json")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["Authorization"], "Bearer saved-demo-token")

    def test_get_remote_platform_auth_status_reports_saved_login(self):
        with mock.patch(
            "backend.app.api.auth.get_platform_auth",
            return_value={
                "username": "Zephyr",
                "token": "saved-demo-token",
                "saved_at": "2026-05-01T00:00:00+00:00",
            },
        ):
            result = auth.get_remote_platform_auth_status()

        self.assertEqual(result["status"], "success")
        self.assertTrue(result["authenticated"])
        self.assertEqual(result["username"], "Zephyr")
        self.assertEqual(result["saved_at"], "2026-05-01T00:00:00+00:00")

    def test_get_remote_platform_auth_status_clears_expired_jwt(self):
        expired_token = make_jwt_with_exp(datetime.now(timezone.utc).timestamp() - 60)

        with mock.patch(
            "backend.app.api.auth.get_platform_auth",
            return_value={
                "username": "Zephyr",
                "token": expired_token,
                "saved_at": "2026-05-01T00:00:00+00:00",
            },
        ), mock.patch("backend.app.api.auth.clear_platform_auth") as clear_platform_auth_mock:
            result = auth.get_remote_platform_auth_status()

        self.assertEqual(result["status"], "success")
        self.assertFalse(result["authenticated"])
        self.assertEqual(result["username"], "")
        self.assertEqual(result["saved_at"], "")
        clear_platform_auth_mock.assert_called_once()

    def test_logout_remote_platform_clears_saved_auth(self):
        with mock.patch("backend.app.api.auth.clear_platform_auth") as clear_platform_auth_mock:
            result = auth.logout_remote_platform()

        self.assertEqual(result["status"], "success")
        self.assertFalse(result["authenticated"])
        self.assertEqual(result["username"], "")
        self.assertEqual(result["saved_at"], "")
        clear_platform_auth_mock.assert_called_once()

    def test_list_remote_projects_uses_saved_token_and_extracts_options(self):
        captured = {}

        def fake_urlopen(remote_request, timeout):
            headers = {key.lower(): value for key, value in remote_request.header_items()}
            captured["url"] = remote_request.full_url
            captured["authorization"] = headers.get("authorization")
            captured["timeout"] = timeout
            return FakeHTTPResponse(200, {
                "data": [
                    {"id": 11, "name": "Android TV"},
                    {"id": 12, "name": "OTT Smoke"},
                    {"name": "Missing Id"},
                ]
            })

        with mock.patch("backend.app.api.auth.get_platform_auth", return_value={"token": "saved-demo-token"}), mock.patch(
            "backend.app.api.auth.request.urlopen",
            side_effect=fake_urlopen,
        ):
            result = auth.list_remote_projects()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["projects"], [
            {"id": 11, "name": "Android TV"},
            {"id": 12, "name": "OTT Smoke"},
        ])
        self.assertEqual(captured["url"], auth.TMS_PROJECTS_URL)
        self.assertEqual(captured["authorization"], "Bearer saved-demo-token")
        self.assertEqual(captured["timeout"], auth.TMS_LOGIN_TIMEOUT)

    def test_list_remote_modules_flattens_tree_names(self):
        captured = {}

        def fake_urlopen(remote_request, timeout):
            captured["url"] = remote_request.full_url
            return FakeHTTPResponse(200, {
                "data": [
                    {
                        "name": "Root",
                        "children": [
                            {"name": "Smoke"},
                            {"name": "Regression", "children": [{"name": "Audio"}]},
                        ],
                    }
                ]
            })

        with mock.patch("backend.app.api.auth.get_platform_auth", return_value={"token": "saved-demo-token"}), mock.patch(
            "backend.app.api.auth.request.urlopen",
            side_effect=fake_urlopen,
        ):
            result = auth.list_remote_modules(project_ids="12")

        parsed_url = parse.urlparse(captured["url"])
        self.assertEqual(parsed_url.path, "/api/modules/tree")
        self.assertEqual(parse.parse_qs(parsed_url.query), {"project_ids": ["12"]})
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["modules"], [
            {"name": "Root", "value": "Root"},
            {"name": "Smoke", "value": "Smoke"},
            {"name": "Regression", "value": "Regression"},
            {"name": "Audio", "value": "Audio"},
        ])

    def test_list_remote_testcases_passes_required_query_params(self):
        captured = {}

        def fake_urlopen(remote_request, timeout):
            captured["url"] = remote_request.full_url
            return FakeHTTPResponse(200, {
                "data": {
                    "list": [
                        {"id": 101, "case_number": "CASE-101", "name": "Login case"},
                        {"id": 102, "meta": {"case_number": "CASE-102"}},
                    ],
                    "total": 18,
                }
            })

        with mock.patch("backend.app.api.auth.get_platform_auth", return_value={"token": "saved-demo-token"}), mock.patch(
            "backend.app.api.auth.request.urlopen",
            side_effect=fake_urlopen,
        ):
            result = auth.list_remote_testcases(project_ids="88", module="Smoke", size=50)

        parsed_url = parse.urlparse(captured["url"])
        self.assertEqual(parsed_url.path, "/api/testcases")
        self.assertEqual(parse.parse_qs(parsed_url.query), {
            "project_ids": ["88"],
            "module": ["Smoke"],
            "size": ["50"],
            "page": ["1"],
        })
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total"], 18)
        self.assertEqual(result["case_numbers"], ["CASE-101", "CASE-102"])
        # 即使上游缺少 precondition / steps，新接口也要返回结构化 testcases 列表
        self.assertEqual(len(result["testcases"]), 2)
        self.assertEqual(result["testcases"][0]["case_number"], "CASE-101")

    def test_list_remote_projects_requires_saved_token(self):
        with mock.patch("backend.app.api.auth.get_platform_auth", return_value={}):
            with self.assertRaises(HTTPException) as context:
                auth.list_remote_projects()

        self.assertEqual(context.exception.status_code, 401)
        self.assertIn("请先在首页完成平台登录", context.exception.detail)

    def test_login_to_remote_platform_saves_token_for_future_reuse(self):
        with mock.patch(
            "backend.app.api.auth.post_tms_login",
            return_value=(200, {"data": {"token": "saved-token-123"}}),
        ), mock.patch("backend.app.api.auth.set_platform_auth") as set_platform_auth_mock:
            result = asyncio.run(
                auth.login_to_remote_platform(
                    auth.TmsLoginRequest(username="Zephyr", password="Whaletv123456")
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertTrue(result["token_saved"])
        self.assertEqual(result["saved_username"], "Zephyr")
        set_platform_auth_mock.assert_called_once()
        saved_state = set_platform_auth_mock.call_args.args[0]
        self.assertEqual(saved_state["username"], "Zephyr")
        self.assertEqual(saved_state["token"], "saved-token-123")
        self.assertEqual(saved_state["login_url"], auth.TMS_LOGIN_URL)


if __name__ == "__main__":
    unittest.main()