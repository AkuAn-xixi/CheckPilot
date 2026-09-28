import contextlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.app.api import asr
from backend.app.services.asr_service import (
    TRANSCRIPT_SILENT_REASON,
    TranscriptionResult,
)


class FakeRequest:
    async def is_disconnected(self):
        return False


class FakeRecorder:
    def __init__(self):
        self.started = False
        self.stopped = False

    def start_recording(self):
        self.started = True

    def stop_recording(self):
        self.stopped = True


async def _noop_wait(*args, **kwargs):
    return None


async def _fake_stream_row_command_events(valid_rows, row_index, request=None):
    yield {"status": "info", "message": f"执行命令 {row_index}"}


def build_fake_stream_row_command_events(executed_batches: list[list[str]]):
    async def _fake_stream(valid_rows, row_index, request=None):
        commands = list(valid_rows[0].get("commands", []))
        executed_batches.append(commands)
        for command in commands:
            yield {"status": "info", "message": f"执行命令 {command}"}

    return _fake_stream


def parse_sse_payload(sse_message: str) -> dict:
    prefix = "data: "
    if not sse_message.startswith(prefix):
        raise AssertionError(f"unexpected sse message: {sse_message}")
    return json.loads(sse_message[len(prefix):].strip())


class AsrExecutionStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_execute_asr_commands_stream_reports_missing_dependencies_before_execution(self):
        request = FakeRequest()
        valid_rows = [{"title": "case-1", "commands": ["OK/1/1"]}]

        with mock.patch.object(asr.asr_service, "get_active_model", return_value={"name": "demo", "path": "demo"}), \
             mock.patch.object(asr.asr_service, "get_runtime_dependency_status", return_value={"missing": ["sounddevice"], "ready": False, "available": {}}):
            events = []
            async for payload in asr.execute_asr_commands_stream(request, "demo.xlsx", 1, valid_rows):
                events.append(parse_sse_payload(payload))

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["status"], "error")
        self.assertIn("sounddevice", events[0]["message"])

    async def test_execute_asr_commands_stream_prefers_excel_reference_over_device_log_tts(self):
        request = FakeRequest()
        valid_rows = [{"title": "case-1", "commands": ["HOME/1/1", "OK/1/1"], "tts_text": "hello world"}]
        recorder = FakeRecorder()
        fake_controller = mock.Mock()
        fake_controller.get_last_tts_text.return_value = "tts sample text"

        with mock.patch.object(asr.asr_service, "get_active_model", return_value={"name": "demo", "path": "demo"}), \
             mock.patch.object(asr.asr_service, "get_runtime_dependency_status", return_value={"missing": [], "ready": True, "available": {}}), \
             mock.patch.object(asr.asr_service, "create_recorder", return_value=recorder), \
             mock.patch.object(asr.asr_service, "save_audio_recording", return_value="audio/case-1.wav"), \
             mock.patch.object(asr.asr_service, "transcribe_audio", return_value=TranscriptionResult(text="hello world")), \
             mock.patch.object(asr.asr_service, "save_transcript", return_value="results/transcript_case-1.txt"), \
             mock.patch.object(asr.asr_service, "compare_transcript", return_value={
                 "cosine": 1.0,
                 "sequence": 1.0,
                 "average": 1.0,
                 "threshold": 0.9,
                 "matched": True,
                 "result": "PASS",
             }), \
             mock.patch.object(asr.asr_service, "save_compare_report", return_value="results/compare_case-1.txt"), \
             mock.patch.object(asr.asr_service, "reduce_noise"), \
             mock.patch("backend.app.api.asr.get_controller", return_value=fake_controller), \
             mock.patch("backend.app.api.asr.wait_with_cancellation", new=_noop_wait), \
             mock.patch("backend.app.api.asr.stream_row_command_events", new=_fake_stream_row_command_events):
            events = []
            async for payload in asr.execute_asr_commands_stream(request, "demo.xlsx", 1, valid_rows):
                events.append(parse_sse_payload(payload))

        self.assertTrue(recorder.started)
        self.assertTrue(recorder.stopped)
        self.assertGreaterEqual(len(events), 5)
        final_event = events[-1]
        self.assertEqual(final_event["status"], "success")
        self.assertEqual(final_event["asr_result"], "PASS")
        self.assertAlmostEqual(final_event["asr_score"], 1.0)
        self.assertEqual(final_event["transcribed_text"], "hello world")
        self.assertEqual(final_event["tts_text"], "tts sample text")
        # 设备日志与 Excel 参考列同时存在时，用户手填的参考列优先，
        # 比对文本与来源标签均指向参考列；抓到的日志 TTS 仍照常回传供前端展示
        self.assertEqual(final_event["reference_text"], "hello world")
        self.assertEqual(final_event["comparison_source"], "reference")
        self.assertEqual(final_event["reference_path"], "Excel TTS 参考列")
        self.assertTrue(any(event.get("tts_text") == "tts sample text" for event in events))
        self.assertTrue(any(
            "已捕获 TTS 输出，按优先级改用 Excel TTS 参考列比对" in event.get("message", "")
            for event in events
        ))

    async def test_execute_asr_commands_stream_tts_marker_records_only_next_command(self):
        request = FakeRequest()
        valid_rows = [{"title": "case-1", "commands": ["HOME/1/1", "TTS", "OK/1/1", "BACK/1/1"]}]
        recorder = FakeRecorder()
        fake_controller = mock.Mock()
        fake_controller.get_last_tts_text.return_value = "tts sample text"
        executed_batches = []
        fake_stream = build_fake_stream_row_command_events(executed_batches)

        with mock.patch.object(asr.asr_service, "get_active_model", return_value={"name": "demo", "path": "demo"}), \
             mock.patch.object(asr.asr_service, "get_runtime_dependency_status", return_value={"missing": [], "ready": True, "available": {}}), \
             mock.patch.object(asr.asr_service, "create_recorder", return_value=recorder), \
             mock.patch.object(asr.asr_service, "save_audio_recording", return_value="audio/case-1.wav"), \
             mock.patch.object(asr.asr_service, "transcribe_audio", return_value=TranscriptionResult(text="hello world")), \
             mock.patch.object(asr.asr_service, "save_transcript", return_value="results/transcript_case-1.txt"), \
             mock.patch.object(asr.asr_service, "compare_transcript", return_value={
                 "cosine": 1.0,
                 "sequence": 1.0,
                 "average": 1.0,
                 "threshold": 0.9,
                 "matched": True,
                 "result": "PASS",
             }), \
             mock.patch.object(asr.asr_service, "save_compare_report", return_value="results/compare_case-1.txt"), \
             mock.patch.object(asr.asr_service, "reduce_noise"), \
             mock.patch("backend.app.api.asr.get_controller", return_value=fake_controller), \
             mock.patch("backend.app.api.asr.wait_with_cancellation", new=_noop_wait), \
             mock.patch("backend.app.api.asr.stream_row_command_events", new=fake_stream):
            events = []
            async for payload in asr.execute_asr_commands_stream(request, "demo.xlsx", 1, valid_rows):
                events.append(parse_sse_payload(payload))

        self.assertTrue(recorder.started)
        self.assertTrue(recorder.stopped)
        # 录音窗口只含 TTS 标记后的第一条指令；post 命令在段比对完成后单独执行
        self.assertEqual(executed_batches, [["HOME/1/1"], ["OK/1/1"], ["BACK/1/1"]])
        # 段成功事件先于 post 命令发出，末尾事件应是最后一条 post 指令的执行信息
        self.assertEqual(events[-1]["status"], "info")
        self.assertIn("BACK/1/1", events[-1]["message"])
        self.assertTrue(any(event.get("status") == "success" for event in events))

    async def test_execute_asr_commands_stream_uses_device_log_tts_when_excel_reference_missing(self):
        request = FakeRequest()
        valid_rows = [{"title": "case-1", "commands": ["HOME/1/1", "OK/1/1"]}]
        recorder = FakeRecorder()
        fake_controller = mock.Mock()
        fake_controller.get_last_tts_text.return_value = "hello world"

        with mock.patch.object(asr.asr_service, "get_active_model", return_value={"name": "demo", "path": "demo"}), \
             mock.patch.object(asr.asr_service, "get_runtime_dependency_status", return_value={"missing": [], "ready": True, "available": {}}), \
             mock.patch.object(asr.asr_service, "create_recorder", return_value=recorder), \
             mock.patch.object(asr.asr_service, "save_audio_recording", return_value="audio/case-1.wav"), \
             mock.patch.object(asr.asr_service, "transcribe_audio", return_value=TranscriptionResult(text="hello world")), \
             mock.patch.object(asr.asr_service, "save_transcript", return_value="results/transcript_case-1.txt"), \
             mock.patch.object(asr.asr_service, "compare_transcript", return_value={
                 "cosine": 1.0,
                 "sequence": 1.0,
                 "average": 1.0,
                 "threshold": 0.9,
                 "matched": True,
                 "result": "PASS",
             }) as compare_mock, \
             mock.patch.object(asr.asr_service, "save_compare_report", return_value="results/compare_case-1.txt"), \
             mock.patch.object(asr.asr_service, "reduce_noise"), \
             mock.patch("backend.app.api.asr.get_controller", return_value=fake_controller), \
             mock.patch("backend.app.api.asr.wait_with_cancellation", new=_noop_wait), \
             mock.patch("backend.app.api.asr.stream_row_command_events", new=_fake_stream_row_command_events):
            events = []
            async for payload in asr.execute_asr_commands_stream(request, "demo.xlsx", 1, valid_rows):
                events.append(parse_sse_payload(payload))

        # 未显式传阈值时使用默认判定阈值 0.5
        compare_mock.assert_called_once_with("hello world", "hello world", threshold=0.5)
        self.assertTrue(any("TTS 输出文本: hello world" in event.get("message", "") for event in events))
        # 参考列为空才回落到日志 TTS，不应出现任何「以参考列比对」的提示
        self.assertFalse(any("Excel TTS 参考列" in event.get("message", "") for event in events))
        final_event = events[-1]
        self.assertEqual(final_event["status"], "success")
        self.assertEqual(final_event["comparison_source"], "tts")
        self.assertEqual(final_event["reference_text"], "hello world")
        self.assertEqual(final_event["tts_text"], "hello world")

    async def test_execute_asr_commands_stream_applies_frontend_match_threshold(self):
        request = FakeRequest()
        valid_rows = [{"title": "case-1", "commands": ["HOME/1/1", "OK/1/1"], "tts_text": "hello world"}]
        recorder = FakeRecorder()
        fake_controller = mock.Mock()
        fake_controller.get_last_tts_text.return_value = "hello world"

        with mock.patch.object(asr.asr_service, "get_active_model", return_value={"name": "demo", "path": "demo"}), \
             mock.patch.object(asr.asr_service, "get_runtime_dependency_status", return_value={"missing": [], "ready": True, "available": {}}), \
             mock.patch.object(asr.asr_service, "create_recorder", return_value=recorder), \
             mock.patch.object(asr.asr_service, "save_audio_recording", return_value="audio/case-1.wav"), \
             mock.patch.object(asr.asr_service, "transcribe_audio", return_value=TranscriptionResult(text="hello world")), \
             mock.patch.object(asr.asr_service, "save_transcript", return_value="results/transcript_case-1.txt"), \
             mock.patch.object(asr.asr_service, "compare_transcript", return_value={
                 "cosine": 1.0,
                 "sequence": 1.0,
                 "average": 1.0,
                 "threshold": 0.9,
                 "matched": True,
                 "result": "PASS",
             }) as compare_mock, \
             mock.patch.object(asr.asr_service, "save_compare_report", return_value="results/compare_case-1.txt"), \
             mock.patch.object(asr.asr_service, "reduce_noise"), \
             mock.patch("backend.app.api.asr.get_controller", return_value=fake_controller), \
             mock.patch("backend.app.api.asr.wait_with_cancellation", new=_noop_wait), \
             mock.patch("backend.app.api.asr.stream_row_command_events", new=_fake_stream_row_command_events):
            events = []
            async for payload in asr.execute_asr_commands_stream(
                request, "demo.xlsx", 1, valid_rows, match_threshold=0.6
            ):
                events.append(parse_sse_payload(payload))

        # 前端执行设置传入的阈值必须真正作用于判定
        compare_mock.assert_called_once_with("hello world", "hello world", threshold=0.6)
        final_event = events[-1]
        self.assertEqual(final_event["status"], "success")
        # 参考列已填写，即便日志 TTS 文本相同也标记为参考列来源
        self.assertEqual(final_event["comparison_source"], "reference")

    async def test_execute_asr_commands_stream_uses_excel_reference_when_no_tts_log(self):
        request = FakeRequest()
        # 参考列（tvm）有手填内容时以它为准，与设备日志抓没抓到 TTS 无关
        valid_rows = [{"title": "case-1", "commands": ["HOME/1/1", "OK/1/1"], "tts_text": "volume Twenty Four"}]
        recorder = FakeRecorder()
        fake_controller = mock.Mock()
        fake_controller.get_last_tts_text.return_value = ""

        with mock.patch.object(asr.asr_service, "get_active_model", return_value={"name": "demo", "path": "demo"}), \
             mock.patch.object(asr.asr_service, "get_runtime_dependency_status", return_value={"missing": [], "ready": True, "available": {}}), \
             mock.patch.object(asr.asr_service, "create_recorder", return_value=recorder), \
             mock.patch.object(asr.asr_service, "save_audio_recording", return_value="audio/case-1.wav"), \
             mock.patch.object(asr.asr_service, "transcribe_audio", return_value=TranscriptionResult(text="hello world")), \
             mock.patch.object(asr.asr_service, "save_transcript", return_value="results/transcript_case-1.txt"), \
             mock.patch.object(asr.asr_service, "compare_transcript", return_value={
                 "cosine": 1.0,
                 "sequence": 1.0,
                 "average": 1.0,
                 "threshold": 0.9,
                 "matched": True,
                 "result": "PASS",
             }) as compare_mock, \
             mock.patch.object(asr.asr_service, "save_compare_report", return_value="results/compare_case-1.txt"), \
             mock.patch.object(asr.asr_service, "reduce_noise"), \
             mock.patch("backend.app.api.asr.get_controller", return_value=fake_controller), \
             mock.patch("backend.app.api.asr.wait_with_cancellation", new=_noop_wait), \
             mock.patch("backend.app.api.asr.stream_row_command_events", new=_fake_stream_row_command_events):
            events = []
            async for payload in asr.execute_asr_commands_stream(request, "demo.xlsx", 1, valid_rows):
                events.append(parse_sse_payload(payload))

        # 参考列路径同样使用默认判定阈值 0.5（两路阈值统一）
        compare_mock.assert_called_once_with("hello world", "volume Twenty Four", threshold=0.5)
        self.assertTrue(any(
            "未捕获到 TTS 输出文本，使用 Excel TTS 参考列进行比对" in event.get("message", "")
            for event in events
        ))
        final_event = events[-1]
        self.assertEqual(final_event["status"], "success")
        self.assertEqual(final_event["comparison_source"], "reference")
        self.assertEqual(final_event["reference_path"], "Excel TTS 参考列")
        self.assertEqual(final_event["reference_text"], "volume Twenty Four")
        self.assertEqual(final_event["tts_text"], "")

    async def test_execute_asr_commands_stream_records_no_ref_when_recognition_unavailable(self):
        """录音静音导致识别不可用时记 NO_REF，不比对、不计入通过率分母。"""
        request = FakeRequest()
        valid_rows = [{"title": "case-1", "commands": ["HOME/1/1", "OK/1/1"], "tts_text": "Flowers"}]
        recorder = FakeRecorder()
        fake_controller = mock.Mock()
        fake_controller.get_last_tts_text.return_value = ""

        with mock.patch.object(asr.asr_service, "get_active_model", return_value={"name": "demo", "path": "demo"}), \
             mock.patch.object(asr.asr_service, "get_runtime_dependency_status", return_value={"missing": [], "ready": True, "available": {}}), \
             mock.patch.object(asr.asr_service, "create_recorder", return_value=recorder), \
             mock.patch.object(asr.asr_service, "save_audio_recording", return_value="audio/case-1.wav"), \
             mock.patch.object(asr.asr_service, "transcribe_audio", return_value=TranscriptionResult(
                 unavailable_reason=TRANSCRIPT_SILENT_REASON
             )), \
             mock.patch.object(asr.asr_service, "compare_transcript") as compare_mock, \
             mock.patch.object(asr.asr_service, "reduce_noise"), \
             mock.patch("backend.app.api.asr.get_controller", return_value=fake_controller), \
             mock.patch("backend.app.api.asr.wait_with_cancellation", new=_noop_wait), \
             mock.patch("backend.app.api.asr.stream_row_command_events", new=_fake_stream_row_command_events):
            events = []
            async for payload in asr.execute_asr_commands_stream(request, "demo.xlsx", 1, valid_rows):
                events.append(parse_sse_payload(payload))

        compare_mock.assert_not_called()
        final_event = events[-1]
        self.assertEqual(final_event["asr_result"], "NO_REF")
        self.assertEqual(final_event["transcribed_text"], TRANSCRIPT_SILENT_REASON)
        self.assertIn(TRANSCRIPT_SILENT_REASON, final_event["message"])


def build_happy_path_patchers(recorder: FakeRecorder, controller: mock.Mock, compare_result: str) -> list:
    """构造一次完整 ASR 校验所需的桩（音频处理/识别/比对全部成功）。

    Args:
        recorder: 假录音器。
        controller: 假 ADB 控制器，需预设 get_last_tts_text 返回值。
        compare_result: compare_transcript 的结论，PASS 或 FAIL。

    Returns:
        尚未启动的 patcher 列表，交由调用方用 ExitStack 统一启停。
    """
    matched = compare_result == "PASS"
    return [
        mock.patch.object(asr.asr_service, "get_active_model", return_value={"name": "demo", "path": "demo"}),
        mock.patch.object(asr.asr_service, "get_runtime_dependency_status", return_value={"missing": [], "ready": True, "available": {}}),
        mock.patch.object(asr.asr_service, "create_recorder", return_value=recorder),
        mock.patch.object(asr.asr_service, "save_audio_recording", return_value="audio/case-1.wav"),
        mock.patch.object(asr.asr_service, "transcribe_audio", return_value=TranscriptionResult(text="hello world")),
        mock.patch.object(asr.asr_service, "save_transcript", return_value="results/transcript_case-1.txt"),
        mock.patch.object(asr.asr_service, "compare_transcript", return_value={
            "cosine": 1.0 if matched else 0.1,
            "sequence": 1.0 if matched else 0.1,
            "average": 1.0 if matched else 0.1,
            "threshold": 0.9,
            "matched": matched,
            "result": compare_result,
        }),
        mock.patch.object(asr.asr_service, "save_compare_report", return_value="results/compare_case-1.txt"),
        mock.patch.object(asr.asr_service, "reduce_noise"),
        mock.patch("backend.app.api.asr.get_controller", return_value=controller),
        mock.patch("backend.app.api.asr.wait_with_cancellation", new=_noop_wait),
    ]


def build_stop_on_post_commands_stream():
    """在后置命令阶段抛出停止异常，用于验证「整行没跑完不写回」。"""

    async def _fake_stream(valid_rows, row_index, request=None):
        commands = list(valid_rows[0].get("commands", []))
        if commands == ["BACK/1/1"]:
            raise asr.ExecutionStopped()
        for command in commands:
            yield {"status": "info", "message": f"执行命令 {command}"}

    return _fake_stream


class AsrTestResultWriteBackTests(unittest.IsolatedAsyncioTestCase):
    """ASR 汇总结论回填 testResult 列：聚合规则、行号换算、写失败不阻断执行。"""

    def test_aggregate_verdict_fails_when_any_judged_segment_fails(self):
        # 任一段 FAIL 即整行 FAIL：多数段通过不再把失败抹平
        self.assertEqual(asr._aggregate_verdict(["PASS", "PASS", "FAIL", "FAIL", "FAIL"]), "FAIL")

    def test_aggregate_verdict_fails_on_single_failing_segment(self):
        # 5 段只失败 1 段（通过率 80%）同样判 FAIL，不给通过率留放水空间
        self.assertEqual(
            asr._aggregate_verdict(["PASS", "PASS", "PASS", "PASS", "FAIL"]),
            "FAIL",
        )

    def test_aggregate_verdict_passes_when_every_judged_segment_passes(self):
        self.assertEqual(asr._aggregate_verdict(["PASS", "PASS", "PASS"]), "PASS")

    def test_aggregate_verdict_ignores_no_ref_segments(self):
        # NO_REF 段既不参与判定也不拉低结论，只有可判定段全过才判 PASS
        self.assertEqual(asr._aggregate_verdict(["PASS", "NO_REF", "NO_REF"]), "PASS")
        self.assertEqual(asr._aggregate_verdict(["FAIL", "NO_REF"]), "FAIL")

    def test_aggregate_verdict_reports_no_ref_when_no_judgeable_segment(self):
        # 只有 NO_REF 或完全没有段时无法判定，不给出 PASS/FAIL 结论
        self.assertEqual(asr._aggregate_verdict(["NO_REF", "NO_REF"]), "NO_REF")
        self.assertEqual(asr._aggregate_verdict([]), "NO_REF")

    def test_write_skips_when_executed_row_has_no_row_number(self):
        with mock.patch.object(asr.excel_service, "write_cell") as write_mock:
            result = asr._write_asr_test_result("demo.xlsx", {"title": "case-1"}, ["PASS"])

        self.assertIsNone(result)
        write_mock.assert_not_called()

    def test_write_skips_when_no_segment_verdict(self):
        with mock.patch.object(asr.excel_service, "write_cell") as write_mock:
            result = asr._write_asr_test_result("demo.xlsx", {"title": "case-1", "row": 5}, [])

        self.assertIsNone(result)
        write_mock.assert_not_called()

    def test_write_failure_returns_none_without_raising(self):
        # 表格被 Excel 占用等写入失败只记录日志，不能让已跑完的校验在界面上报错
        with mock.patch.object(asr.excel_service, "write_cell", side_effect=OSError("文件被占用")):
            result = asr._write_asr_test_result("demo.xlsx", {"title": "case-1", "row": 5}, ["PASS"])

        self.assertIsNone(result)

    async def test_stream_writes_pass_back_to_test_result_column(self):
        request = FakeRequest()
        # row=5 是含表头的 Excel 行号，回填下标应为 3
        valid_rows = [{"title": "case-1", "row": 5, "commands": ["HOME/1/1", "OK/1/1"], "tts_text": "hello world"}]
        recorder = FakeRecorder()
        fake_controller = mock.Mock()
        fake_controller.get_last_tts_text.return_value = "hello world"

        with contextlib.ExitStack() as stack:
            for patcher in build_happy_path_patchers(recorder, fake_controller, compare_result="PASS"):
                stack.enter_context(patcher)
            stack.enter_context(mock.patch("backend.app.api.asr.stream_row_command_events", new=_fake_stream_row_command_events))
            write_mock = stack.enter_context(mock.patch.object(asr.excel_service, "write_cell"))

            async for _ in asr.execute_asr_commands_stream(request, "demo.xlsx", 1, valid_rows):
                pass

        write_mock.assert_called_once_with("demo.xlsx", "testResult", 3, "PASS")

    async def test_stream_writes_fail_when_comparison_fails(self):
        request = FakeRequest()
        valid_rows = [{"title": "case-1", "row": 5, "commands": ["HOME/1/1", "OK/1/1"], "tts_text": "hello world"}]
        recorder = FakeRecorder()
        fake_controller = mock.Mock()
        fake_controller.get_last_tts_text.return_value = "hello world"

        with contextlib.ExitStack() as stack:
            for patcher in build_happy_path_patchers(recorder, fake_controller, compare_result="FAIL"):
                stack.enter_context(patcher)
            stack.enter_context(mock.patch("backend.app.api.asr.stream_row_command_events", new=_fake_stream_row_command_events))
            write_mock = stack.enter_context(mock.patch.object(asr.excel_service, "write_cell"))

            async for _ in asr.execute_asr_commands_stream(request, "demo.xlsx", 1, valid_rows):
                pass

        write_mock.assert_called_once_with("demo.xlsx", "testResult", 3, "FAIL")

    async def test_stream_skips_write_when_user_stops_before_run_finishes(self):
        request = FakeRequest()
        valid_rows = [{"title": "case-1", "row": 5, "commands": ["HOME/1/1", "TTS", "OK/1/1", "BACK/1/1"], "tts_text": "hello world"}]
        recorder = FakeRecorder()
        fake_controller = mock.Mock()
        fake_controller.get_last_tts_text.return_value = "hello world"

        with contextlib.ExitStack() as stack:
            for patcher in build_happy_path_patchers(recorder, fake_controller, compare_result="PASS"):
                stack.enter_context(patcher)
            stack.enter_context(mock.patch("backend.app.api.asr.stream_row_command_events", new=build_stop_on_post_commands_stream()))
            write_mock = stack.enter_context(mock.patch.object(asr.excel_service, "write_cell"))

            async for _ in asr.execute_asr_commands_stream(request, "demo.xlsx", 1, valid_rows):
                pass

        # 段结论已产出但整行没跑完，不应把半截结果记进表格
        write_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()