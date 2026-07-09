import asyncio
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


if __name__ == "__main__":
    unittest.main()