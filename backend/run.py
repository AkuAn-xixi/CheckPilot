"""应用启动脚本"""
import logging
import os
import socket
import sys

import uvicorn

_log = logging.getLogger(__name__)

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)

#: 开发态监听地址与端口。
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8003
#: 端口探测连的是回环地址：``0.0.0.0`` 是监听地址，不能作为连接目标。
PORT_PROBE_HOST = "127.0.0.1"
#: 探测超时（秒）。只用来判断端口是否被占用，不需要等业务响应。
PORT_PROBE_TIMEOUT_SECONDS = 1.0


def _is_port_in_use(port: int) -> bool:
    """判断端口是否已被其他进程监听。

    用主动连接而不是 ``bind`` 试探：Windows 上 ``SO_REUSEADDR`` 允许第二个
    socket 绑定已被监听的端口，``bind`` 成功并不能证明端口空闲。而旧实例一旦
    僵死（事件循环被饿死，只完成 TCP 握手却不回响应），"连得上"依然成立，
    所以主动连接比 bind 探测更可靠。

    Args:
        port: 待探测的端口。

    Returns:
        端口已被占用返回 True，空闲返回 False。
    """
    try:
        with socket.create_connection(
            (PORT_PROBE_HOST, port), timeout=PORT_PROBE_TIMEOUT_SECONDS
        ):
            return True
    except OSError:
        return False


def _abort_if_port_in_use() -> None:
    """端口被占用时给出排查指引并退出。

    静默双绑定比启动失败危险得多：两个实例同时 LISTENING 时请求落到哪个由内核
    决定，旧实例若已僵死就会挂住接口，在界面上表现为"设备/功能莫名不可用"。
    """
    if not _is_port_in_use(SERVER_PORT):
        return
    _log.error(
        "端口 %d 已被占用，拒绝启动，以免与旧实例同时监听导致请求随机落到对方身上。"
        "请先结束占用该端口的进程（多为上次异常退出的残留实例，它可能仍在监听却"
        "不响应任何请求）。排查: netstat -ano | findstr :%d",
        SERVER_PORT,
        SERVER_PORT,
    )
    sys.exit(1)


if __name__ == "__main__":
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    _abort_if_port_in_use()

    # 延迟到 sys.path 补齐之后再导入：直接执行 ``python backend/run.py`` 时
    # sys.path[0] 是 backend/ 而非项目根目录，模块顶层导入 ``backend.*`` 会失败。
    from backend.app.utils.uvicorn_logging import build_uvicorn_log_config

    uvicorn.run(
        "backend.main:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=True,
        reload_dirs=[BACKEND_DIR],
        log_level="info",
        log_config=build_uvicorn_log_config(),
    )
