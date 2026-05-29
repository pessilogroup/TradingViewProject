"""
server/workers/liveness_monitor.py — Cross-Server Health Monitor (V2 Hardened).

Runs on SERVER C and periodically checks /health on SERVER A and SERVER B.
Sends Telegram alerts when a server goes down and again when it recovers.

Usage (via APScheduler in server/scheduler.py):
    from workers.liveness_monitor import run_liveness_check
    scheduler.add_job(run_liveness_check, "interval", minutes=5, id="liveness_check")

Or standalone test:
    python -m server.workers.liveness_monitor

Environment variables:
  SERVER_A_HEALTH_URL  — e.g. http://100.x.x.1:5000/health  (Tailscale IP)
  SERVER_B_HEALTH_URL  — e.g. http://100.x.x.2:5002/health  (Tailscale IP)
  LIVENESS_ALERT_AFTER_FAILURES = 2   (alert after N consecutive failures)
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import List, Optional

import httpx

log = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
ALERT_AFTER_FAILURES = int(os.getenv("LIVENESS_ALERT_AFTER_FAILURES", "2"))
RECOVERY_NOTIFY      = True
CHECK_TIMEOUT_SEC    = 10.0


# ── Server health tracker ──────────────────────────────────────────────────────

@dataclass
class ServerHealth:
    """Track health state of a single server endpoint."""
    name:                  str
    url:                   str
    consecutive_failures:  int   = 0
    last_success:          float = 0.0
    last_check:            float = 0.0
    is_healthy:            bool  = True
    last_error:            str   = ""


# Dynamic server list — read from env so Tailscale IPs can be configured
# without code changes.
def _build_server_list() -> List[ServerHealth]:
    servers = []
    a_url = os.getenv("SERVER_A_HEALTH_URL", "")
    b_url = os.getenv("SERVER_B_HEALTH_URL", "")
    if a_url:
        servers.append(ServerHealth(name="SERVER_A (Gateway)", url=a_url))
    if b_url:
        servers.append(ServerHealth(name="SERVER_B (Execution Vault)", url=b_url))
    if not servers:
        log.warning(
            "[LivenessMonitor] SERVER_A_HEALTH_URL and SERVER_B_HEALTH_URL not set. "
            "No servers will be monitored."
        )
    return servers


# Module-level server list (initialised on first check)
_servers: Optional[List[ServerHealth]] = None


def _get_servers() -> List[ServerHealth]:
    global _servers
    if _servers is None:
        _servers = _build_server_list()
    return _servers


# ── Main check function ────────────────────────────────────────────────────────

async def run_liveness_check() -> None:
    """Check /health on all configured servers.

    Called by APScheduler every 5 minutes (or standalone).
    """
    servers = _get_servers()
    if not servers:
        return

    async with httpx.AsyncClient(timeout=CHECK_TIMEOUT_SEC) as client:
        for server in servers:
            server.last_check = time.time()
            try:
                resp = await client.get(server.url)
                data = resp.json()

                if resp.status_code == 200 and data.get("status") in ("healthy", "ok"):
                    was_unhealthy = not server.is_healthy
                    server.is_healthy            = True
                    server.consecutive_failures  = 0
                    server.last_success          = time.time()
                    server.last_error            = ""

                    uptime    = data.get("uptime_seconds", "?")
                    pending   = data.get("pending_count", "?")
                    log.info(
                        f"✅ {server.name} healthy "
                        f"(uptime={uptime}s, pending={pending})"
                    )

                    if was_unhealthy and RECOVERY_NOTIFY:
                        await _send_recovery_alert(server, data)
                else:
                    await _handle_failure(
                        server, f"Degraded response: {data.get('status','?')}"
                    )

            except httpx.ConnectError as exc:
                await _handle_failure(server, f"Connection refused ({exc})")
            except httpx.ReadTimeout:
                await _handle_failure(
                    server, f"Read timeout (>{CHECK_TIMEOUT_SEC}s)"
                )
            except Exception as exc:
                await _handle_failure(server, str(exc)[:200])


async def _handle_failure(server: ServerHealth, error: str) -> None:
    server.consecutive_failures += 1
    server.is_healthy = True if server.consecutive_failures == 0 else False
    server.last_error = error
    log.warning(
        f"❌ {server.name} FAILED "
        f"(attempt #{server.consecutive_failures}): {error}"
    )
    if server.consecutive_failures >= ALERT_AFTER_FAILURES:
        await _send_down_alert(server, error)


async def _send_down_alert(server: ServerHealth, error: str) -> None:
    downtime_min = 0
    if server.last_success > 0:
        downtime_min = int((time.time() - server.last_success) / 60)

    msg = (
        f"🚨 <b>SERVER DOWN</b>\n\n"
        f"Server: <b>{server.name}</b>\n"
        f"URL: <code>{server.url}</code>\n"
        f"Lỗi: {error}\n"
        f"Failures: {server.consecutive_failures} liên tiếp\n"
        f"Downtime: ~{downtime_min} phút\n\n"
        f"⚠️ Signal pipeline có thể bị gián đoạn!"
    )
    try:
        from notifier import notify_all
        await notify_all(msg)
    except Exception as exc:
        log.error(f"[LivenessMonitor] Failed to send down alert: {exc}")


async def _send_recovery_alert(server: ServerHealth, health_data: dict) -> None:
    msg = (
        f"✅ <b>SERVER RECOVERED</b>\n\n"
        f"Server: <b>{server.name}</b>\n"
        f"Status: healthy\n"
        f"Uptime: {health_data.get('uptime_seconds', 0)}s\n"
        f"Pending signals: {health_data.get('pending_count', '?')}"
    )
    try:
        from notifier import notify_all
        await notify_all(msg)
    except Exception as exc:
        log.error(f"[LivenessMonitor] Failed to send recovery alert: {exc}")


# ── Standalone entry-point ─────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_liveness_check())
