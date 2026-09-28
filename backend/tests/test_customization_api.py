import unittest
from unittest import mock

from fastapi import HTTPException

from backend.app.api.customization import (
    DEFAULT_VALID_KEYS,
    ColorVerifyConfigUpdateRequest,
    CreateSchemeRequest,
    CustomCommandsUpdateRequest,
    DuplicateSchemeRequest,
    KeyCodesUpdateRequest,
    VerifyEngineConfigUpdateRequest,
    _normalize_config,
    create_scheme,
    delete_custom_command,
    delete_key_code,
    duplicate_scheme,
    get_color_verify_config_route,
    get_key_codes,
    get_valid_keys,
    get_verify_engine_config_route,
    list_schemes,
    reset_custom_commands,
    reset_key_codes,
    reset_valid_keys,
    update_color_verify_config_route,
    update_custom_commands,
    update_key_codes,
    update_verify_engine_config_route,
)
from backend.app.utils.adb_controller import KEYCODE_MAP


def _config_with_scheme() -> dict:
    return {
        "active_scheme": "默认",
        "schemes": {
            "默认": {
                "valid_keys": ["HOME", "OK"],
                "key_codes": {"HOME": 3, "OK": 23},
            }
        },
        "extra_command_delay": 0.0,
    }


class ColorVerifyConfigApiTests(unittest.TestCase):
    def setUp(self):
        self.config = _config_with_scheme()

    @mock.patch("backend.app.api.customization._save_config")
    def test_get_returns_defaults(self, _mock_save):
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            result = get_color_verify_config_route()
        self.assertEqual(result, {
            "color_min_similarity": 0.4,
            "color_weight": 0.2,
            "feature_min_similarity": 0.3,
        })

    @mock.patch("backend.app.api.customization._save_config")
    def test_put_updates_only_provided_fields(self, mock_save):
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            result = update_color_verify_config_route(
                ColorVerifyConfigUpdateRequest(feature_min_similarity=0.5)
            )
        self.assertEqual(result, {
            "color_min_similarity": 0.4,
            "color_weight": 0.2,
            "feature_min_similarity": 0.5,
        })
        self.assertEqual(self.config["feature_min_similarity"], 0.5)
        mock_save.assert_called_once_with(self.config)

    @mock.patch("backend.app.api.customization._save_config")
    def test_put_clamps_out_of_range_values(self, _mock_save):
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            result = update_color_verify_config_route(
                ColorVerifyConfigUpdateRequest(
                    color_min_similarity=2.0,
                    color_weight=-1,
                    feature_min_similarity=0.9,
                )
            )
        self.assertEqual(result, {
            "color_min_similarity": 0.4,
            "color_weight": 0.2,
            "feature_min_similarity": 0.9,
        })


class CustomCommandsApiTests(unittest.TestCase):
    def setUp(self):
        self.config = _config_with_scheme()

    @mock.patch("backend.app.api.customization._save_config")
    def test_update_persists_and_merges_valid_keys(self, mock_save):
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            result = update_custom_commands("默认", CustomCommandsUpdateRequest(
                custom_commands={"CLAERNETFLIX": "adb shell am force-stop com.netflix.ninja"}
            ))

        self.assertEqual(result["custom_commands"], {
            "CLAERNETFLIX": "adb shell am force-stop com.netflix.ninja",
        })
        # 键名自动并入合法按键，保证 Excel 校验/回放不被当作无效按键
        self.assertIn("CLAERNETFLIX", self.config["schemes"]["默认"]["valid_keys"])
        # 原始 valid_keys 应保留
        self.assertIn("HOME", self.config["schemes"]["默认"]["valid_keys"])
        mock_save.assert_called_once_with(self.config)

    def test_rejects_newline_command(self):
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            with self.assertRaises(HTTPException) as ctx:
                update_custom_commands("默认", CustomCommandsUpdateRequest(
                    custom_commands={"BAD": "shell am start\nrm -rf /"}
                ))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_rejects_empty_command(self):
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            with self.assertRaises(HTTPException):
                update_custom_commands("默认", CustomCommandsUpdateRequest(
                    custom_commands={"EMPTY": "   "}
                ))

    @mock.patch("backend.app.api.customization._save_config")
    def test_delete_removes_single_command(self, mock_save):
        self.config["schemes"]["默认"]["custom_commands"] = {
            "CLAERNETFLIX": "adb shell am force-stop com.netflix.ninja",
            "CLEARYOUTUBE": "adb shell am force-stop com.google.android.youtube",
        }
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            result = delete_custom_command("默认", "CLAERNETFLIX")

        self.assertEqual(result["custom_commands"], {
            "CLEARYOUTUBE": "adb shell am force-stop com.google.android.youtube",
        })

    def test_delete_missing_command_raises_404(self):
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            with self.assertRaises(HTTPException) as ctx:
                delete_custom_command("默认", "NOPE")
        self.assertEqual(ctx.exception.status_code, 404)

    @mock.patch("backend.app.api.customization._save_config")
    def test_reset_clears_all(self, mock_save):
        self.config["schemes"]["默认"]["custom_commands"] = {
            "CLAERNETFLIX": "adb shell am force-stop com.netflix.ninja",
        }
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            result = reset_custom_commands("默认")

        self.assertEqual(result["custom_commands"], {})
        self.assertNotIn("custom_commands", self.config["schemes"]["默认"])


def _legacy_scheme_config() -> dict:
    """老配置：方案里没有 inherit_defaults 标记，应当继续继承内置默认表。"""
    return {
        "active_scheme": "老方案",
        "schemes": {"老方案": {}},
    }


class BlankSchemeTests(unittest.TestCase):
    """新建方案不继承默认按键表与 KEYCODE_MAP，从空表开始等捕获/导入填充。"""

    def setUp(self):
        self.config = _legacy_scheme_config()

    @mock.patch("backend.app.api.customization._save_config")
    def test_created_scheme_is_marked_as_not_inheriting(self, _mock_save):
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            create_scheme(CreateSchemeRequest(name="新遥控器"))

        self.assertEqual(self.config["schemes"]["新遥控器"], {"inherit_defaults": False})

    @mock.patch("backend.app.api.customization._save_config")
    def test_created_scheme_reports_no_valid_keys(self, _mock_save):
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            create_scheme(CreateSchemeRequest(name="新遥控器"))
            result = get_valid_keys("新遥控器")

        self.assertEqual(result["keys"], [])

    @mock.patch("backend.app.api.customization._save_config")
    def test_created_scheme_reports_no_key_codes(self, _mock_save):
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            create_scheme(CreateSchemeRequest(name="新遥控器"))
            result = get_key_codes("新遥控器")

        self.assertEqual(result["key_codes"], {})
        self.assertEqual(result["custom_overrides"], {})

    @mock.patch("backend.app.api.customization._save_config")
    def test_created_scheme_counts_as_zero_in_scheme_list(self, _mock_save):
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            create_scheme(CreateSchemeRequest(name="新遥控器"))
            listed = list_schemes()

        counts = {s["name"]: s["valid_keys_count"] for s in listed["schemes"]}
        self.assertEqual(counts["新遥控器"], 0)
        self.assertEqual(counts["老方案"], len(DEFAULT_VALID_KEYS))

    @mock.patch("backend.app.api.customization._save_config")
    def test_legacy_scheme_still_inherits_defaults(self, _mock_save):
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            keys = get_valid_keys("老方案")
            codes = get_key_codes("老方案")

        self.assertEqual(keys["keys"], DEFAULT_VALID_KEYS)
        self.assertEqual(codes["key_codes"], dict(sorted(KEYCODE_MAP.items())))

    @mock.patch("backend.app.api.customization._save_config")
    def test_capture_into_new_scheme_keeps_only_captured_entries(self, _mock_save):
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            create_scheme(CreateSchemeRequest(name="新遥控器"))
            result = update_key_codes("新遥控器", KeyCodesUpdateRequest(key_codes={"HOME": 3}))

        self.assertEqual(result["key_codes"], {"HOME": 3})
        self.assertEqual(self.config["schemes"]["新遥控器"]["valid_keys"], ["HOME"])

    @mock.patch("backend.app.api.customization._save_config")
    def test_capture_into_legacy_scheme_still_merges_defaults(self, _mock_save):
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            result = update_key_codes("老方案", KeyCodesUpdateRequest(key_codes={"HOME": 3}))

        self.assertEqual(result["key_codes"], dict(sorted({**KEYCODE_MAP, "HOME": 3}.items())))
        self.assertIn("OK", self.config["schemes"]["老方案"]["valid_keys"])

    @mock.patch("backend.app.api.customization._save_config")
    def test_reset_on_new_scheme_returns_empty_tables(self, _mock_save):
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            create_scheme(CreateSchemeRequest(name="新遥控器"))
            update_key_codes("新遥控器", KeyCodesUpdateRequest(key_codes={"HOME": 3}))
            keys = reset_valid_keys("新遥控器")
            codes = reset_key_codes("新遥控器")

        self.assertEqual(keys["keys"], [])
        self.assertEqual(codes["key_codes"], {})

    @mock.patch("backend.app.api.customization._save_config")
    def test_deleting_last_capture_on_new_scheme_leaves_table_empty(self, _mock_save):
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            create_scheme(CreateSchemeRequest(name="新遥控器"))
            update_key_codes("新遥控器", KeyCodesUpdateRequest(key_codes={"HOME": 3}))
            result = delete_key_code("新遥控器", "HOME")

        self.assertEqual(result["key_codes"], {})

    @mock.patch("backend.app.api.customization._save_config")
    def test_duplicate_keeps_the_not_inheriting_marker(self, _mock_save):
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            create_scheme(CreateSchemeRequest(name="新遥控器"))
            duplicate_scheme("新遥控器", DuplicateSchemeRequest(new_name="新遥控器副本"))
            result = get_key_codes("新遥控器副本")

        self.assertEqual(result["key_codes"], {})


class DefaultKeyDeletionTests(unittest.TestCase):
    """删除继承来的默认键：固化当前生效表并脱离继承，否则重读时会被重新合并回来。"""

    def setUp(self):
        self.config = _legacy_scheme_config()

    @mock.patch("backend.app.api.customization._save_config")
    def test_delete_default_key_removes_row_and_detaches_from_defaults(self, _mock_save):
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            result = delete_key_code("老方案", "BACK")

        expected = {k: v for k, v in KEYCODE_MAP.items() if k != "BACK"}
        self.assertEqual(result["key_codes"], dict(sorted(expected.items())))
        self.assertFalse(self.config["schemes"]["老方案"]["inherit_defaults"])

    @mock.patch("backend.app.api.customization._save_config")
    def test_deleted_default_key_does_not_reappear_on_reload(self, _mock_save):
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            delete_key_code("老方案", "BACK")
            reloaded = get_key_codes("老方案")

        self.assertNotIn("BACK", reloaded["key_codes"])

    @mock.patch("backend.app.api.customization._save_config")
    def test_delete_custom_override_keeps_inheriting_defaults(self, _mock_save):
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            update_key_codes("老方案", KeyCodesUpdateRequest(key_codes={"MY_KEY": 900}))
            result = delete_key_code("老方案", "MY_KEY")

        self.assertEqual(result["key_codes"], dict(sorted(KEYCODE_MAP.items())))
        self.assertNotIn("inherit_defaults", self.config["schemes"]["老方案"])

    @mock.patch("backend.app.api.customization._save_config")
    def test_delete_key_absent_from_mapping_raises_not_found(self, _mock_save):
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            with self.assertRaises(HTTPException) as ctx:
                delete_key_code("老方案", "NO_SUCH_KEY")

        self.assertEqual(ctx.exception.status_code, 404)


class VerifyEngineConfigApiTests(unittest.TestCase):
    """图片校验引擎配置：默认值、部分更新、非法回落、以及顶层键不被丢弃。"""

    def setUp(self):
        self.config = _config_with_scheme()

    @mock.patch("backend.app.api.customization._save_config")
    def test_get_returns_defaults_when_keys_absent(self, _mock_save):
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            result = get_verify_engine_config_route()

        self.assertEqual(result, {
            "verify_engine": "opencv",
            "airtest_threshold": 0.85,
            "airtest_rgb": False,
            "airtest_strategy": "tpl",
        })

    @mock.patch("backend.app.api.customization._save_config")
    def test_put_updates_only_provided_fields(self, mock_save):
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            result = update_verify_engine_config_route(
                VerifyEngineConfigUpdateRequest(verify_engine="airtest")
            )

        self.assertEqual(result["verify_engine"], "airtest")
        self.assertEqual(result["airtest_threshold"], 0.85)
        self.assertEqual(self.config["verify_engine"], "airtest")
        mock_save.assert_called_once_with(self.config)

    @mock.patch("backend.app.api.customization._save_config")
    def test_put_clamps_invalid_values_to_defaults(self, _mock_save):
        with mock.patch("backend.app.api.customization._load_config", return_value=self.config):
            result = update_verify_engine_config_route(VerifyEngineConfigUpdateRequest(
                verify_engine="tensorflow",
                airtest_threshold=9.0,
                airtest_strategy="brisk",
            ))

        self.assertEqual(result["verify_engine"], "opencv")
        self.assertEqual(result["airtest_threshold"], 0.85)
        self.assertEqual(result["airtest_strategy"], "tpl")

    @mock.patch("backend.app.api.customization._save_config")
    def test_normalize_config_keeps_engine_keys(self, _mock_save):
        """回归守卫：不在 _normalize_config 返回值里的顶层键会被静默丢弃。"""
        normalized = _normalize_config({
            "verify_engine": "airtest",
            "airtest_threshold": 0.6,
            "airtest_rgb": True,
            "airtest_strategy": "mstpl",
        })

        self.assertEqual(normalized["verify_engine"], "airtest")
        self.assertEqual(normalized["airtest_threshold"], 0.6)
        self.assertTrue(normalized["airtest_rgb"])
        self.assertEqual(normalized["airtest_strategy"], "mstpl")
        # 既有颜色键仍在，新键不是替换而是追加
        self.assertIn("color_min_similarity", normalized)


if __name__ == "__main__":
    unittest.main()
