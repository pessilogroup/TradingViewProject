"""
start_server.py -- Sovereign Server Launcher with SO_REUSEADDR + UTF-8
Prevents zombie socket conflicts and UnicodeEncodeError on Windows cp1252.
Usage: python start_server.py [--port 5000]

SCAR-TVP-001: Never use Start-Process powershell for uvicorn.
              Always run this script directly in the terminal.
"""
import io
import os
import sys
import socket

# ── Force UTF-8 output BEFORE any imports that might log with emoji ──────────
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import uvicorn  # noqa: E402 — must come after encoding fix

port = 5000
for i, arg in enumerate(sys.argv):
    if arg == "--port" and i + 1 < len(sys.argv):
        port = int(sys.argv[i + 1])

# Pre-create socket with SO_REUSEADDR to bypass zombie socket on Windows
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("0.0.0.0", port))
sock.set_inheritable(True)

print(f"[Sovereign Launcher] Port {port} bound with SO_REUSEADDR + UTF-8 OK", flush=True)

config = uvicorn.Config("main:app", host="0.0.0.0", port=port, log_level="info")
server = uvicorn.Server(config)

import asyncio

async def serve():
    config.load()
    server.lifespan = config.lifespan_class(config)
    await server.startup(sockets=[sock])
    await server.main_loop()
    await server.shutdown()

asyncio.run(serve())
