import os
import sys
import time
import socket
import threading
import webbrowser
import uvicorn
from backend.main import app as fastapi_app

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
      with open("adbcontrol_port.txt", "w", encoding="utf-8") as f:
        f.write(str(port))
    except:
      pass
    webbrowser.open(f"http://localhost:{port}")
    if sys.platform.startswith("win"):
      try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, f"ADBControl is running.\nOpen: http://localhost:{port}", "ADBControl", 0)
      except:
        pass
    while not server.should_exit:
      time.sleep(0.5)
  except Exception as e:
    msg = f"Startup failed: {e}"
    try:
      with open("adbcontrol_error.log", "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    except:
      pass
    if sys.platform.startswith("win"):
      try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, msg, "ADBControl", 0)
      except:
        pass
    time.sleep(3)

if __name__ == "__main__":
  main()
