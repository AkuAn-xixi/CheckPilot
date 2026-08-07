import asyncio
import json
import time
import unittest
from unittest import mock

from backend.app.api import execution


class FakeController:
    def __init__(self):
        self.sent = []

    def send_keyevent(self, keycode, keyname, delay=0):
        self.sent.append((keycode, keyname, delay))
        return True

    def take_screenshot(self, _title=None):
        raise AssertionError("execution should stop before taking a screenshot")


class SlowFakeController(FakeController):
    def __init__(self, send_duration: float):
        super().__init__()
        self.send_duration = send_duration

    def send_keyevent(self, keycode, keyname, delay=0):
        time.sleep(self.send_duration)
        return super().send_keyevent(keycode, keyname, delay)


class FakeRequest:
    def __init__(self, disconnect_after: float):
        self.started = time.perf_counter()
        self.disconnect_after = disconnect_after

    async def is_disconnected(self):
        return (time.perf_counter() - self.started) >= self.disconnect_after


class ExecutionStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_execute_commands_stream_stops_during_delay_when_client_disconnects(self):
        fake_controller = FakeController()
        request = FakeRequest(disconnect_after=0.15)
        valid_rows = [{"commands": ["OK/1/2"], "title": "case"}]

        started = time.perf_counter()
        with mock.patch("backend.app.api.execution.get_controller", return_value=fake_controller):
            events = []
            async for payload in execution.execute_commands_stream(request, "demo.xlsx", 1, "demo.xlsx", valid_rows):
                events.append(payload)
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.6)
        self.assertEqual(len(fake_controller.sent), 1)
        self.assertEqual(len(events), 1)

    async def test_stream_row_command_events_emits_keepalive_comments_during_long_delay(self):
        fake_controller = FakeController()
        request = FakeRequest(disconnect_after=60)
        valid_rows = [{"commands": ["OK/1/0.25"], "title": "case"}]

        with mock.patch("backend.app.api.execution.get_controller", return_value=fake_controller), \
             mock.patch("backend.app.api.execution.WAIT_KEEPALIVE_INTERVAL", 0.05):
            events = []
            async for payload in execution.stream_row_command_events(valid_rows, 1, request):
                events.append(payload)

        self.assertEqual(len(fake_controller.sent), 1)
        self.assertTrue(any(isinstance(item, str) and item.startswith(": ") for item in events))

    async def test_stream_row_command_events_treats_delay_as_total_repeat_cadence(self):
        fake_controller = SlowFakeController(send_duration=0.08)
        request = FakeRequest(disconnect_after=60)
        valid_rows = [{"commands": ["DOWN/2/0.3"], "title": "case"}]

        started = time.perf_counter()
        with mock.patch("backend.app.api.execution.get_controller", return_value=fake_controller):
            events = []
            async for payload in execution.stream_row_command_events(valid_rows, 1, request):
                events.append(payload)
        elapsed = time.perf_counter() - started

        self.assertEqual(len(fake_controller.sent), 2)
        self.assertEqual(sum(1 for item in events if isinstance(item, dict) and item.get("message") == "正在发送: DOWN"), 2)
        self.assertLess(elapsed, 0.8)


class ResolveVerifyVerdictTests(unittest.TestCase):
    def test_normal_assert_matched_is_pass(self):
        self.assertTrue(execution.resolve_verify_verdict(matched=True, expect_no_match=False))
        self.assertFalse(execution.resolve_verify_verdict(matched=False, expect_no_match=False))

    def test_not_assert_inverts_verdict(self):
        self.assertTrue(execution.resolve_verify_verdict(matched=False, expect_no_match=True))
        self.assertFalse(execution.resolve_verify_verdict(matched=True, expect_no_match=True))


class NotAssertInvertedVerificationTests(unittest.IsolatedAsyncioTestCase):
    """NOTASSERT 反向断言：图片不匹配 → PASS，图片匹配 → FAIL。"""

    def _fake_controller(self):
        controller = FakeController()
        controller.take_screenshot = lambda _title=None: "C:/fake/screenshot.png"
        return controller

    @staticmethod
    def _parse_sse(payloads):
        events = []
        for payload in payloads:
            if isinstance(payload, str) and payload.startswith("data: "):
                try:
                    events.append(json.loads(payload[len("data: "):].strip()))
                except json.JSONDecodeError:
                    pass
        return events

    async def _run_case(self, matched: bool):
        fake_controller = self._fake_controller()
        request = FakeRequest(disconnect_after=60)
        valid_rows = [{"row": 1, "commands": ["NOTASSERT/1/0"], "title": "case", "verify_image": "target.png"}]
        verify_result = {"success": True, "matched": matched, "score": 0.9 if matched else 0.2}

        payloads = []
        with mock.patch("backend.app.api.execution.get_controller", return_value=fake_controller), \
             mock.patch("backend.app.api.execution.get_custom_commands", return_value={}), \
             mock.patch("backend.app.api.execution.get_keycode_map", return_value={"ASSERT": 0, "NOTASSERT": 0}), \
             mock.patch("backend.app.api.execution.verify_image_base64_match", return_value=verify_result), \
             mock.patch("backend.app.api.execution.asr_service.get_active_model", return_value=None), \
             mock.patch("backend.app.api.execution.excel_service.write_cell"):
            async for payload in execution.execute_commands_stream(
                request, "demo.xlsx", 1, "demo.xlsx", valid_rows,
                verify_image_base64_list=["data:image/png;base64,AAAA"],
                enable_recording=False,
            ):
                payloads.append(payload)

        return self._parse_sse(payloads)

    async def test_not_assert_not_matched_counts_as_pass(self):
        events = await self._run_case(matched=False)
        final = events[-1]
        self.assertEqual(final.get("verify_result"), "PASS", events)
        self.assertEqual(final.get("status"), "success", events)
        self.assertIn("PASS", final.get("message", ""), events)

    async def test_not_assert_matched_counts_as_fail(self):
        events = await self._run_case(matched=True)
        final = events[-1]
        self.assertEqual(final.get("verify_result"), "FAIL", events)
        self.assertEqual(final.get("status"), "error", events)


if __name__ == "__main__":
    unittest.main()