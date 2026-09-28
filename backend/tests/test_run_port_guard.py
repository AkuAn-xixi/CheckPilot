"""``backend/run.py`` 启动端口预检的测试。

覆盖端口探测本身（真实监听 / 已关闭）与占用时的启动拦截。这两个分支是防止
"两个实例静默双绑定"的唯一屏障，回归时必须在测试里锁住。
"""
import socket
import unittest
from unittest import mock

from backend import run

#: 一个只用于 mock 场景的端口号，真实值无关紧要。
UNUSED_TEST_PORT = 59999


class IsPortInUseTests(unittest.TestCase):
    """``_is_port_in_use`` 的端口探测行为。"""

    def test_is_port_in_use_listening_port_returns_true(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind((run.PORT_PROBE_HOST, 0))
            listener.listen(1)
            port = listener.getsockname()[1]

            self.assertTrue(run._is_port_in_use(port))

    def test_is_port_in_use_closed_port_returns_false(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind((run.PORT_PROBE_HOST, 0))
            listener.listen(1)
            port = listener.getsockname()[1]

        self.assertFalse(run._is_port_in_use(port))

    def test_is_port_in_use_connection_refused_returns_false(self) -> None:
        with mock.patch.object(
            run.socket, "create_connection", side_effect=OSError("refused")
        ):
            self.assertFalse(run._is_port_in_use(UNUSED_TEST_PORT))

    def test_is_port_in_use_probe_always_carries_timeout(self) -> None:
        """探测必须带超时：僵死实例仍会完成 TCP 握手，没有超时就会挂住启动流程。"""
        with mock.patch.object(run.socket, "create_connection") as connect:
            run._is_port_in_use(run.SERVER_PORT)

        connect.assert_called_once_with(
            (run.PORT_PROBE_HOST, run.SERVER_PORT),
            timeout=run.PORT_PROBE_TIMEOUT_SECONDS,
        )


class AbortIfPortInUseTests(unittest.TestCase):
    """``_abort_if_port_in_use`` 在端口被占用时的启动拦截。"""

    def test_abort_if_port_in_use_busy_port_exits_with_code_1(self) -> None:
        with (
            mock.patch.object(run, "_is_port_in_use", return_value=True),
            mock.patch.object(run, "_log") as log,
            self.assertRaises(SystemExit) as raised,
        ):
            run._abort_if_port_in_use()

        self.assertEqual(raised.exception.code, 1)
        log.error.assert_called_once()

    def test_abort_if_port_in_use_free_port_keeps_running(self) -> None:
        with mock.patch.object(run, "_is_port_in_use", return_value=False):
            run._abort_if_port_in_use()


if __name__ == "__main__":
    unittest.main()
