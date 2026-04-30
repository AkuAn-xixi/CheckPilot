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


if __name__ == "__main__":
    unittest.main()