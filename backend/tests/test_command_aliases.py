import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from backend.app.utils.command_aliases import (
    MAX_EXPAND_DEPTH,
    expand_command_aliases,
    expand_command_aliases_grouped,
    load_command_aliases,
    split_command_segments,
)

ALIAS_HEADER = ['oriStep', 'Key', 'DESCRIBE']

#: 别名字典模块的 logger 名，用于断言告警是否发出。
ALIAS_LOGGER_NAME = "backend.app.utils.command_aliases"


def _write_workbook(path: Path, sheets: dict) -> None:
    """按 {表名: [[行...], ...]} 建一个多工作表工作簿。"""
    workbook = Workbook()
    workbook.remove(workbook.active)
    for sheet_name, rows in sheets.items():
        worksheet = workbook.create_sheet(title=sheet_name)
        for row in rows:
            worksheet.append(row)
    workbook.save(path)
    workbook.close()


class SplitCommandSegmentsTests(unittest.TestCase):
    def test_drops_blank_segments_and_strips_whitespace(self):
        self.assertEqual(
            split_command_segments("HOME/1/5, ,OK/1/1,"),
            ["HOME/1/5", "OK/1/1"],
        )

    def test_returns_empty_list_for_blank_text(self):
        self.assertEqual(split_command_segments(""), [])


class LoadCommandAliasesTests(unittest.TestCase):
    def test_returns_empty_when_alias_sheet_missing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            excel_path = Path(tmp_dir) / "no_alias.xlsx"
            _write_workbook(
                excel_path, {"OSDCASE": [["runOption", "oriStep"], ["Y", "HOME/1/1"]]}
            )

            self.assertEqual(load_command_aliases(excel_path), {})

    def test_reads_alias_sheet_into_uppercase_keyed_dict(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            excel_path = Path(tmp_dir) / "alias.xlsx"
            _write_workbook(
                excel_path,
                {
                    "OSDCASE": [["runOption", "oriStep"], ["Y", "OPENSETTING"]],
                    "oriStep": [
                        ALIAS_HEADER,
                        ["OPENSETTING", "HOME/1/5,SETTING/1/1,DOWN/9/1,OK/1/1", "打开Setting"],
                        ["OPENPPictureSound", "HOME/1/5,SETTING/1/1", "打开Picture&Sound"],
                    ],
                },
            )

            aliases = load_command_aliases(excel_path)

            self.assertEqual(
                aliases["OPENSETTING"], "HOME/1/5,SETTING/1/1,DOWN/9/1,OK/1/1"
            )
            # 表内是混合大小写，字典键统一大写
            self.assertEqual(aliases["OPENPPICTURESOUND"], "HOME/1/5,SETTING/1/1")

    def test_matches_sheet_name_and_headers_case_insensitively(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            excel_path = Path(tmp_dir) / "alias_case.xlsx"
            _write_workbook(
                excel_path,
                {
                    "OSDCASE": [["runOption", "oriStep"], ["Y", "OPENOK"]],
                    "ORISTEP": [[" ORISTeP ", " KEY "], ["openok", "OK/1/1", "确认"]],
                },
            )

            self.assertEqual(load_command_aliases(excel_path), {"OPENOK": "OK/1/1"})

    def test_keeps_first_value_for_duplicate_alias(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            excel_path = Path(tmp_dir) / "alias_dup.xlsx"
            _write_workbook(
                excel_path,
                {
                    "oriStep": [
                        ALIAS_HEADER,
                        ["OPENDUPE", "HOME/1/1", "第一条"],
                        ["OPENDUPE", "BACK/1/1", "第二条"],
                    ]
                },
            )

            self.assertEqual(load_command_aliases(excel_path), {"OPENDUPE": "HOME/1/1"})

    def test_skips_rows_with_blank_name_or_value(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            excel_path = Path(tmp_dir) / "alias_blank.xlsx"
            _write_workbook(
                excel_path,
                {
                    "oriStep": [
                        ALIAS_HEADER,
                        ["OPENOK", "OK/1/1", "正常"],
                        ["", "HOME/1/1", "别名为空"],
                        ["OPENNOVALUE", None, "按键串为空"],
                    ]
                },
            )

            self.assertEqual(load_command_aliases(excel_path), {"OPENOK": "OK/1/1"})

    def test_preserves_value_case_for_random_repeat_spec(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            excel_path = Path(tmp_dir) / "alias_case_value.xlsx"
            _write_workbook(
                excel_path,
                {
                    "oriStep": [
                        ALIAS_HEADER,
                        ["OPENRANDOM", "DOWN/X:(0:3)/1", "随机次数"],
                    ]
                },
            )

            self.assertEqual(
                load_command_aliases(excel_path), {"OPENRANDOM": "DOWN/X:(0:3)/1"}
            )

    def test_returns_empty_when_headers_unrecognized(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            excel_path = Path(tmp_dir) / "alias_bad_header.xlsx"
            _write_workbook(
                excel_path, {"oriStep": [["名称", "指令"], ["OPENOK", "OK/1/1"]]}
            )

            self.assertEqual(load_command_aliases(excel_path), {})

    def test_returns_empty_when_file_missing(self):
        self.assertEqual(load_command_aliases("not_exists_at_all.xlsx"), {})


class ExpandCommandAliasesTests(unittest.TestCase):
    ALIASES = {"OPENSETTING": "HOME/1/5,SETTING/1/1,DOWN/9/1,OK/1/1"}

    def test_replaces_alias_with_its_key_sequence(self):
        self.assertEqual(
            expand_command_aliases(split_command_segments("OPENSETTING"), self.ALIASES),
            ["HOME/1/5", "SETTING/1/1", "DOWN/9/1", "OK/1/1"],
        )

    def test_supports_mixing_alias_with_plain_commands(self):
        self.assertEqual(
            expand_command_aliases(
                split_command_segments("OPENSETTING,DOWN/1/1"), self.ALIASES
            ),
            ["HOME/1/5", "SETTING/1/1", "DOWN/9/1", "OK/1/1", "DOWN/1/1"],
        )

    def test_matches_alias_name_case_insensitively(self):
        self.assertEqual(
            expand_command_aliases(split_command_segments("opensetting"), self.ALIASES),
            ["HOME/1/5", "SETTING/1/1", "DOWN/9/1", "OK/1/1"],
        )

    def test_keeps_unknown_segment_as_is(self):
        self.assertEqual(
            expand_command_aliases(
                split_command_segments("OPENSETTINGG"), self.ALIASES
            ),
            ["OPENSETTINGG"],
        )

    def test_is_identity_when_no_aliases(self):
        self.assertEqual(
            expand_command_aliases(["HOME/1/1", "OK/1/1"], {}), ["HOME/1/1", "OK/1/1"]
        )

    def test_drops_blank_segments(self):
        self.assertEqual(
            expand_command_aliases(["", "  ", "OK/1/1"], self.ALIASES), ["OK/1/1"]
        )

    def test_resolves_nested_alias(self):
        aliases = {"OPENOUTER": "OPENINNER,DOWN/1/1", "OPENINNER": "HOME/1/1"}

        self.assertEqual(
            expand_command_aliases(["OPENOUTER"], aliases), ["HOME/1/1", "DOWN/1/1"]
        )

    def test_keeps_original_on_self_reference_without_hanging(self):
        self.assertEqual(
            expand_command_aliases(["LOOP"], {"LOOP": "LOOP,OK/1/1"}),
            ["LOOP", "OK/1/1"],
        )

    def test_keeps_original_on_mutual_reference_without_hanging(self):
        self.assertEqual(
            expand_command_aliases(["A"], {"A": "B", "B": "A"}), ["A"]
        )

    def test_stops_expanding_beyond_max_depth(self):
        # A1 -> A2 -> ... -> A6，层级上限内只展开 MAX_EXPAND_DEPTH 层
        aliases = {f"A{index}": f"A{index + 1}" for index in range(1, 6)}
        aliases["A6"] = "OK/1/1"

        self.assertEqual(
            expand_command_aliases(["A1"], aliases), [f"A{MAX_EXPAND_DEPTH + 1}"]
        )

    def test_keeps_segment_when_alias_value_has_no_command(self):
        self.assertEqual(
            expand_command_aliases(["OPENEMPTY"], {"OPENEMPTY": ",,"}), ["OPENEMPTY"]
        )

    def test_expands_alias_followed_by_default_suffix(self):
        # oriStep 列的书写约定就是 KEY/次数/时间，补上 /1/1 是最自然的写法；
        # 按键串末尾本就是 OK/1/1，所以这次补后缀不改变任何一条命令
        self.assertEqual(
            expand_command_aliases(
                split_command_segments("OPENSETTING/1/1"), self.ALIASES
            ),
            ["HOME/1/5", "SETTING/1/1", "DOWN/9/1", "OK/1/1"],
        )

    def test_applies_suffix_delay_to_last_expanded_command(self):
        # /1/3 = 整段执行一次，跑完再等 3 秒。延迟落在末条命令的延迟位上，因为对
        # KEY/次数/延迟 而言那一位本就是「发完这条之后等多久」，而末条发完即整段结束
        self.assertEqual(
            expand_command_aliases(
                split_command_segments("OPENSETTING/1/3"), self.ALIASES
            ),
            ["HOME/1/5", "SETTING/1/1", "DOWN/9/1", "OK/1/3"],
        )

    def test_repeats_whole_sequence_for_suffix_count(self):
        # 次数 = 整段重复几遍；延迟只在最后一遍的末尾生效，不插在中间
        self.assertEqual(
            expand_command_aliases(
                split_command_segments("OPENSETTING/2/3"), self.ALIASES
            ),
            [
                "HOME/1/5", "SETTING/1/1", "DOWN/9/1", "OK/1/1",
                "HOME/1/5", "SETTING/1/1", "DOWN/9/1", "OK/1/3",
            ],
        )

    def test_repeats_without_touching_delay_when_suffix_omits_it(self):
        # NAME/2 只重复、不额外等待，展开结果自身的延迟原样保留
        self.assertEqual(
            expand_command_aliases(["OPENSETTING/2"], self.ALIASES),
            [
                "HOME/1/5", "SETTING/1/1", "DOWN/9/1", "OK/1/1",
                "HOME/1/5", "SETTING/1/1", "DOWN/9/1", "OK/1/1",
            ],
        )

    def test_keeps_segment_when_last_command_cannot_carry_delay(self):
        # 末条是 TTS 这种两段式标记，没有延迟位可写，只能保留原样并告警
        aliases = {"OPENPLAY": "HOME/1/5,TTS"}

        with self.assertLogs(ALIAS_LOGGER_NAME, level="WARNING") as logs:
            expanded = expand_command_aliases(["OPENPLAY/1/3"], aliases)

        self.assertEqual(expanded, ["HOME/1/5", "TTS"])
        self.assertIn("OPENPLAY", "\n".join(logs.output))

    def test_expands_alias_with_suffix_inside_mixed_sequence(self):
        self.assertEqual(
            expand_command_aliases(
                split_command_segments("OPENSETTING/1/1,DOWN/1/1"), self.ALIASES
            ),
            ["HOME/1/5", "SETTING/1/1", "DOWN/9/1", "OK/1/1", "DOWN/1/1"],
        )

    def test_expands_nested_alias_written_with_suffix(self):
        aliases = {"OPENOUTER": "OPENINNER/1/1,DOWN/1/1", "OPENINNER": "HOME/1/1"}

        self.assertEqual(
            expand_command_aliases(["OPENOUTER"], aliases), ["HOME/1/1", "DOWN/1/1"]
        )

    def test_keeps_plain_command_with_suffix_untouched(self):
        self.assertEqual(
            expand_command_aliases(["HOME/1/5", "DOWN/2/1"], self.ALIASES),
            ["HOME/1/5", "DOWN/2/1"],
        )

    def test_keeps_unknown_name_with_suffix_untouched(self):
        self.assertEqual(
            expand_command_aliases(["OPENSETTINGG/1/1"], self.ALIASES),
            ["OPENSETTINGG/1/1"],
        )

    def test_alias_wins_over_same_named_key(self):
        # 别名与真实按键同名时以别名为准，后缀也照样生效（5 秒延迟移到末条）。
        # 所以字典里本就不该出现与按键同名的逻辑名——否则用例里所有 HOME/1/5
        # 都会变成 OK/1/5。
        self.assertEqual(
            expand_command_aliases(["HOME/1/5"], {"HOME": "OK/1/1"}), ["OK/1/5"]
        )

    def test_same_named_key_is_untouched_when_dictionary_omits_it(self):
        self.assertEqual(
            expand_command_aliases(["HOME/1/5"], {"OPENHOME": "OK/1/1"}),
            ["HOME/1/5"],
        )

    def test_does_not_warn_for_ordinary_suffix(self):
        # 补后缀是这一列的书写习惯，只在真出问题时告警，不在正常用例上刷日志
        with self.assertNoLogs(ALIAS_LOGGER_NAME, level="WARNING"):
            expand_command_aliases(["OPENSETTING/1/3"], self.ALIASES)

    def test_keeps_segment_when_suffix_repeat_is_not_a_plain_count(self):
        # 随机次数对「整段导航」没有明确定义（随机重复整段？），不猜语义，
        # 保留原文让下游按既有规则报错
        with self.assertLogs(ALIAS_LOGGER_NAME, level="WARNING") as logs:
            expanded = expand_command_aliases(["OPENSETTING/X:(1:3)/1"], self.ALIASES)

        self.assertEqual(expanded, ["OPENSETTING/X:(1:3)/1"])
        self.assertIn("OPENSETTING", "\n".join(logs.output))


class ExpandCommandAliasesGroupedTests(unittest.TestCase):
    ALIASES = {"OPENSETTING": "HOME/1/5,SETTING/1/1,DOWN/9/1,OK/1/1"}

    def test_keeps_each_segment_together_with_its_expansion(self):
        self.assertEqual(
            expand_command_aliases_grouped(
                split_command_segments("OPENSETTING/1/1,DOWN/2/1"), self.ALIASES
            ),
            [
                ("OPENSETTING/1/1", ["HOME/1/5", "SETTING/1/1", "DOWN/9/1", "OK/1/1"]),
                ("DOWN/2/1", ["DOWN/2/1"]),
            ],
        )

    def test_drops_blank_segments_and_strips_whitespace(self):
        self.assertEqual(
            expand_command_aliases_grouped(["", "  ", " OK/1/1 "], {}),
            [("OK/1/1", ["OK/1/1"])],
        )

    def test_returns_empty_list_for_no_segments(self):
        self.assertEqual(expand_command_aliases_grouped([], self.ALIASES), [])

    def test_every_group_expands_to_at_least_one_command(self):
        # 展开不了的段原样保留，因此不会出现空分组——调用方的 offsets 才能严格递增
        grouped = expand_command_aliases_grouped(
            ["OPENSETTINGG", "LOOP"], {"LOOP": "LOOP,OK/1/1"}
        )

        self.assertTrue(all(commands for _segment, commands in grouped))

    def test_flattening_agrees_with_expand_command_aliases(self):
        segments = split_command_segments("OPENSETTING/1/3,DOWN/2/1")

        grouped = expand_command_aliases_grouped(segments, self.ALIASES)

        self.assertEqual(
            [command for _segment, commands in grouped for command in commands],
            expand_command_aliases(segments, self.ALIASES),
        )


if __name__ == "__main__":
    unittest.main()
