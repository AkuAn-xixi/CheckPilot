"""uvicorn 日志配置：为访问日志补上时间戳。

uvicorn 默认的 ``access`` formatter 格式串里没有时间字段，访问日志因此只有先后
顺序、没有时刻。本项目其余日志统一带 ``%(asctime)s``，两者混在同一份日志文件里
时无法按时间对齐，"某个请求到底等了多久"就看不出来。这里只替换 formatter 的格式
串，handler、logger 层级、``disable_existing_loggers`` 等仍沿用 uvicorn 默认值。
"""
import copy
from typing import Any, Dict

from uvicorn.config import LOGGING_CONFIG

#: 与 ``backend/main.py``、``run_app.py`` 中根 logger 的格式保持一致。
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

#: uvicorn 默认配置里需要改写格式串的 formatter：``access`` 是请求日志，
#: ``default`` 是 uvicorn 自身的启动/报错日志。
_LOG_FORMATTER_NAMES = ("default", "access")


def build_uvicorn_log_config() -> Dict[str, Any]:
    """返回在 uvicorn 默认配置基础上补齐时间戳的日志配置。

    Returns:
        可直接传给 ``uvicorn.run(log_config=...)`` 或
        ``uvicorn.Config(log_config=...)`` 的配置字典。返回的是深拷贝，
        不会改动 uvicorn 的全局 ``LOGGING_CONFIG``。
    """
    log_config = copy.deepcopy(LOGGING_CONFIG)
    for formatter_name in _LOG_FORMATTER_NAMES:
        log_config["formatters"][formatter_name]["fmt"] = LOG_FORMAT
    return log_config
