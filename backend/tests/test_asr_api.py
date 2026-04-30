import json
import unittest
from unittest import mock

from backend.app.api import asr


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
            async for payload in asr.execute_asr_commands_stream(request, 1, valid_rows):
                events.append(parse_sse_payload(payload))

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["status"], "error")
        self.assertIn("sounddevice", events[0]["message"])

    async def test_execute_asr_commands_stream_emits_compare_result(self):
        request = FakeRequest()
        valid_rows = [{"title": "case-1", "commands": ["HOME/1/1", "OK/1/1"]}]
        recorder = FakeRecorder()
        fake_controller = mock.Mock()
        fake_controller.get_last_tts_text.return_value = "tts sample text"

        with mock.patch.object(asr.asr_service, "get_active_model", return_value={"name": "demo", "path": "demo"}), \
             mock.patch.object(asr.asr_service, "get_runtime_dependency_status", return_value={"missing": [], "ready": True, "available": {}}), \
             mock.patch.object(asr.asr_service, "find_reference", return_value={"path": "references/case-1.txt", "text": "hello world"}), \
             mock.patch.object(asr.asr_service, "create_recorder", return_value=recorder), \
             mock.patch.object(asr.asr_service, "save_audio_recording", return_value="audio/case-1.wav"), \
             mock.patch.object(asr.asr_service, "transcribe_audio", return_value="hello world"), \
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
             mock.patch("backend.app.api.asr.get_controller", return_value=fake_controller), \
             mock.patch("backend.app.api.asr.wait_with_cancellation", new=_noop_wait), \
             mock.patch("backend.app.api.asr.stream_row_command_events", new=_fake_stream_row_command_events):
            events = []
            async for payload in asr.execute_asr_commands_stream(request, 1, valid_rows):
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
        self.assertEqual(final_event["reference_text"], "hello world")
        self.assertTrue(any(event.get("tts_text") == "tts sample text" for event in events))

    async def test_execute_asr_commands_stream_uses_explicit_tts_marker_window(self):
        request = FakeRequest()
        valid_rows = [{"title": "case-1", "commands": ["HOME/1/1", "TTS", "OK/1/1", "BACK/1/1"]}]
        recorder = FakeRecorder()
        fake_controller = mock.Mock()
        fake_controller.get_last_tts_text.return_value = "tts sample text"
        executed_batches = []
        fake_stream = build_fake_stream_row_command_events(executed_batches)

        with mock.patch.object(asr.asr_service, "get_active_model", return_value={"name": "demo", "path": "demo"}), \
             mock.patch.object(asr.asr_service, "get_runtime_dependency_status", return_value={"missing": [], "ready": True, "available": {}}), \
             mock.patch.object(asr.asr_service, "find_reference", return_value={"path": "references/case-1.txt", "text": "hello world"}), \
             mock.patch.object(asr.asr_service, "create_recorder", return_value=recorder), \
             mock.patch.object(asr.asr_service, "save_audio_recording", return_value="audio/case-1.wav"), \
             mock.patch.object(asr.asr_service, "transcribe_audio", return_value="hello world"), \
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
             mock.patch("backend.app.api.asr.get_controller", return_value=fake_controller), \
             mock.patch("backend.app.api.asr.wait_with_cancellation", new=_noop_wait), \
             mock.patch("backend.app.api.asr.stream_row_command_events", new=fake_stream):
            events = []
            async for payload in asr.execute_asr_commands_stream(request, 1, valid_rows):
                events.append(parse_sse_payload(payload))

        self.assertTrue(recorder.started)
        self.assertTrue(recorder.stopped)
        self.assertEqual(executed_batches, [["HOME/1/1"], ["OK/1/1"], ["BACK/1/1"]])
        self.assertTrue(any("识别到 TTS 标记" in event.get("message", "") for event in events))
        self.assertTrue(any("继续执行剩余命令" in event.get("message", "") for event in events))
        self.assertEqual(events[-1]["status"], "success")

    async def test_execute_asr_commands_stream_falls_back_to_tts_text_when_reference_missing(self):
        request = FakeRequest()
        valid_rows = [{"title": "case-1", "commands": ["HOME/1/1", "OK/1/1"]}]
        recorder = FakeRecorder()
        fake_controller = mock.Mock()
        fake_controller.get_last_tts_text.return_value = "hello world"

        with mock.patch.object(asr.asr_service, "get_active_model", return_value={"name": "demo", "path": "demo"}), \
             mock.patch.object(asr.asr_service, "get_runtime_dependency_status", return_value={"missing": [], "ready": True, "available": {}}), \
             mock.patch.object(asr.asr_service, "find_reference", return_value=None), \
             mock.patch.object(asr.asr_service, "create_recorder", return_value=recorder), \
             mock.patch.object(asr.asr_service, "save_audio_recording", return_value="audio/case-1.wav"), \
             mock.patch.object(asr.asr_service, "transcribe_audio", return_value="hello world"), \
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
             mock.patch("backend.app.api.asr.get_controller", return_value=fake_controller), \
             mock.patch("backend.app.api.asr.wait_with_cancellation", new=_noop_wait), \
             mock.patch("backend.app.api.asr.stream_row_command_events", new=_fake_stream_row_command_events):
            events = []
            async for payload in asr.execute_asr_commands_stream(request, 1, valid_rows):
                events.append(parse_sse_payload(payload))

        compare_mock.assert_called_once_with("hello world", "hello world")
        self.assertTrue(any("改用 TTS 输出文本进行比对" in event.get("message", "") for event in events))
        final_event = events[-1]
        self.assertEqual(final_event["status"], "success")
        self.assertEqual(final_event["comparison_source"], "tts")
        self.assertEqual(final_event["reference_text"], "hello world")
        self.assertEqual(final_event["tts_text"], "hello world")


if __name__ == "__main__":
    unittest.main()