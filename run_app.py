import os
import sys
import time
import socket
import threading
import logging
import webbrowser
import uvicorn
from datetime import datetime

# 打包（frozen）后 __file__ 指向 PyInstaller 解压临时目录 _MEIPASS，日志必须写到
# exe 所在目录，而不是临时目录（退出即被清空）。开发模式下仍用项目根目录。
if getattr(sys, "frozen", False):
  ROOT_DIR = os.path.dirname(sys.executable)
else:
  ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if ROOT_DIR not in sys.path:
  sys.path.insert(0, ROOT_DIR)
if BACKEND_DIR not in sys.path:
  sys.path.insert(0, BACKEND_DIR)

# ---- 日志文件配置（在导入业务模块之前完成，确保所有 logger 都能写入文件） ----
LOG_DIR = os.path.join(ROOT_DIR, "log")
os.makedirs(LOG_DIR, exist_ok=True)
_log_filename = datetime.now().strftime("AutoDeck_%Y%m%d_%H%M%S.log")
_log_filepath = os.path.join(LOG_DIR, _log_filename)

_file_handler = logging.FileHandler(_log_filepath, encoding="utf-8")
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

_console_handler = logging.StreamHandler(sys.stderr)
_console_handler.setLevel(logging.INFO)
_console_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

logging.basicConfig(level=logging.INFO, handlers=[_file_handler, _console_handler])

# uvicorn 的 access log 也写入同一文件
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)

# 过滤 Windows Proactor 事件循环的连接重置噪音：播放/拖动录屏视频时浏览器
# 用 Range 分块拉流（206），进度切换或关闭播放器会让连接被强制关闭（WinError 10054），
# asyncio 的 _call_connection_lost 回调会打 ERROR 刷屏，实际不影响运行。
class _AsyncioConnectionResetFilter(logging.Filter):
    def filter(self, record):
        if record.name == 'asyncio':
            message = record.getMessage()
            if '_call_connection_lost' in message or 'WinError 10054' in message or 'ConnectionResetError' in message:
                return False
        return True

logging.getLogger('asyncio').addFilter(_AsyncioConnectionResetFilter())

from backend.main import app as fastapi_app
from backend.app.config import settings

def find_port(start=8000, end=8010):
  for p in range(start, end + 1):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
      s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
      try:
        s.bind(("0.0.0.0", p))
        return p
      except OSError:
        continue
  return start

def run_server(port):
  config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=port, log_level="info")
  server = uvicorn.Server(config)
  t = threading.Thread(target=server.run, daemon=True)
  t.start()
  return server

def main():
  try:
    port = find_port()
    server = run_server(port)
    time.sleep(1.2)
    try:
      with open(settings.WORKING_DIR / "adbcontrol_port.txt", "w", encoding="utf-8") as f:
        f.write(str(port))
    except:
      pass
    webbrowser.open(f"http://localhost:{port}")
    if sys.platform.startswith("win"):
      try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, f"AutoDeck 自动测控台 is running.\nOpen: http://localhost:{port}", "AutoDeck", 0)
      except:
        pass
    while not server.should_exit:
      time.sleep(0.5)
  except Exception as e:
    msg = f"Startup failed: {e}"
    try:
      with open(settings.WORKING_DIR / "adbcontrol_error.log", "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    except:
      pass
    if sys.platform.startswith("win"):
      try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, msg, "AutoDeck", 0)
      except:
        pass
    time.sleep(3)

if __name__ == "__main__":
  main()
