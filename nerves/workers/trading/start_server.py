"""
start_server.py -- Sovereign Server Launcher with SO_REUSEADDR + UTF-8
Prevents zombie socket conflicts and UnicodeEncodeError on Windows cp1252.
Usage: python start_server.py [--port 5000] [--kill]

SCAR-TVP-001: Never use Start-Process powershell for uvicorn.
              Always run this script directly in the terminal.
SCAR-TVP-002: Always kill existing process on port before binding.
              Old process = stale code in memory → fixes 401/409 zombie bugs.
"""
import io
import os
import sys
import socket
import subprocess

# ── Force UTF-8 output BEFORE any imports that might log with emoji ──────────
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

port = 5000
kill_only = False
for i, arg in enumerate(sys.argv):
    if arg == "--port" and i + 1 < len(sys.argv):
        port = int(sys.argv[i + 1])
    if arg == "--kill":
        kill_only = True


def _kill_port(p: int) -> None:
    """Kill any process currently listening on port p (Windows + Linux)."""
    killed = False
    try:
        # Windows: netstat + taskkill
        out = subprocess.check_output(
            ["netstat", "-ano"], text=True, stderr=subprocess.DEVNULL
        )
        for line in out.splitlines():
            if f":{p} " in line and "LISTENING" in line:
                parts = line.split()
                proc_id = parts[-1].strip()
                if proc_id.isdigit():
                    subprocess.run(
                        ["taskkill", "/PID", proc_id, "/F"],
                        capture_output=True,
                    )
                    print(f"[Sovereign Launcher] Killed stale PID {proc_id} on :{p}", flush=True)
                    killed = True
    except Exception as e:
        print(f"[Sovereign Launcher] kill_port warning: {e}", flush=True)
    if not killed:
        print(f"[Sovereign Launcher] No stale process on :{p}", flush=True)


# ── SCAR-TVP-002: Kill stale server before binding ───────────────────────────
_kill_port(port)

if kill_only:
    print("[Sovereign Launcher] --kill done. Exiting.", flush=True)
    sys.exit(0)

import uvicorn  # noqa: E402 — must come after encoding fix
import asyncio  # noqa: E402

# Pre-create socket with SO_REUSEADDR to bypass zombie socket on Windows
import time as _time
_time.sleep(0.5)  # brief pause after kill for OS to release port
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("0.0.0.0", port))
sock.set_inheritable(True)

print(f"[Sovereign Launcher] Port {port} bound with SO_REUSEADDR + UTF-8 OK", flush=True)

config = uvicorn.Config("main:app", host="0.0.0.0", port=port, log_level="info")
server = uvicorn.Server(config)


async def serve():
    config.load()
    server.lifespan = config.lifespan_class(config)
    await server.startup(sockets=[sock])
    await server.main_loop()
    await server.shutdown()


asyncio.run(serve())
