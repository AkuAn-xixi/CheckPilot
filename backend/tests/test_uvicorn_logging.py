"""``uvicorn`` 访问日志时间戳的测试。

访问日志没有时间字段时，它和业务日志只能按先后顺序读，"某个请求到底等了多久"
就得不结论。这里锁住两件事：配置产出的格式串确实带 ``%(asctime)s``，且该格式串
喂给 uvicorn 自己的 formatter 能渲染成带时间的行——formatter 会改写日志记录内容，
格式串写错在这里就会暴露，而不是等到线上看到一行没有时间的日志。
"""
import logging
import unittest

from uvicorn.config import LOGGING_CONFIG
from uvicorn.logging import AccessFormatter, DefaultFormatter

from backend.app.utils.uvicorn_logging import build_uvicorn_log_config

#: ``logging.Formatter`` 默认的 asctime 形状，用于断言日志行以时间开头。
ASCTIME_PATTERN = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - "


def _build_access_record() -> logging.LogRecord:
    """构造一条与 uvicorn 真实访问日志同形状的记录。"""
    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1:5968", "GET", "/api/devices/list", "1.1", 200),
        exc_info=None,
    )


def _build_error_record() -> logging.LogRecord:
    """构造一条 uvicorn 自身生命周期日志同形状的记录。"""
    return logging.LogRecord(
        name="uvicorn.error",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Application startup complete.",
        args=None,
        exc_info=None,
    )


class BuildUvicornLogConfigTests(unittest.TestCase):
    """``build_uvicorn_log_config`` 产出的配置内容。"""

    def test_build_uvicorn_log_config_formatters_carry_timestamp(self) -> None:
        config = build_uvicorn_log_config()

        self.assertIn("%(asctime)s", config["formatters"]["access"]["fmt"])
        self.assertIn("%(asctime)s", config["formatters"]["default"]["fmt"])

    def test_build_uvicorn_log_config_keeps_uvicorn_wiring(self) -> None:
        """只换格式串：formatter 工厂、handler、logger 层级都沿用 uvicorn 默认。"""
        config = build_uvicorn_log_config()

        self.assertEqual(
            config["formatters"]["access"]["()"], "uvicorn.logging.AccessFormatter"
        )
        self.assertFalse(config["disable_existing_loggers"])
        self.assertEqual(config["handlers"], LOGGING_CONFIG["handlers"])
        self.assertEqual(config["loggers"], LOGGING_CONFIG["loggers"])

    def test_build_uvicorn_log_config_does_not_mutate_uvicorn_defaults(self) -> None:
        """改写的是副本：uvicorn 的全局配置不能被就地修改。"""
        original_access_fmt = LOGGING_CONFIG["formatters"]["access"]["fmt"]
        original_default_fmt = LOGGING_CONFIG["formatters"]["default"]["fmt"]

        build_uvicorn_log_config()

        self.assertEqual(
            LOGGING_CONFIG["formatters"]["access"]["fmt"], original_access_fmt
        )
        self.assertEqual(
            LOGGING_CONFIG["formatters"]["default"]["fmt"], original_default_fmt
        )


class RenderUvicornRecordTests(unittest.TestCase):
    """格式串经 uvicorn 真实 formatter 渲染后的输出。"""

    def test_access_record_renders_with_leading_timestamp(self) -> None:
        config = build_uvicorn_log_config()
        formatter = AccessFormatter(
            fmt=config["formatters"]["access"]["fmt"], use_colors=False
        )

        output = formatter.format(_build_access_record())

        self.assertRegex(output, ASCTIME_PATTERN)
        self.assertIn('"GET /api/devices/list HTTP/1.1" 200', output)

    def test_error_record_renders_with_leading_timestamp(self) -> None:
        config = build_uvicorn_log_config()
        formatter = DefaultFormatter(
            fmt=config["formatters"]["default"]["fmt"], use_colors=False
        )

        output = formatter.format(_build_error_record())

        self.assertRegex(output, ASCTIME_PATTERN)
        self.assertIn("Application startup complete.", output)


if __name__ == "__main__":
    unittest.main()
