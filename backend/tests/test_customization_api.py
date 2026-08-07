import unittest
from unittest import mock

from fastapi import HTTPException

from backend.app.api.customization import (
    ColorVerifyConfigUpdateRequest,
    CustomCommandsUpdateRequest,
    delete_custom_command,
    get_color_verify_config_route,
    reset_custom_commands,
    update_color_verify_config_route,
    update_custom_commands,
)


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


if __name__ == "__main__":
    unittest.main()
