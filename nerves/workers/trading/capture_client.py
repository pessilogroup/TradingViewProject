"""
P11 — PythonCaptureClient
Thin async HTTP adapter that communicates with the CaptureDaemon (Node.js).
Falls back to legacy subprocess mode (MCPClient._run) if daemon is unreachable.

Design ref: design.md § "PythonCaptureClient"
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path

import config

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CaptureRequest:
    """Capture request parameters sent to the daemon."""
    symbol: str = "active"
    timeframe: str = "active"
    region: str = "chart"
    crop: bool = True
    skip_if_same: bool = True


@dataclass
class CaptureResult:
    """Result from a capture operation (daemon or fallback)."""
    success: bool
    file_path: Optional[str] = None
    base64: Optional[str] = None
    size_bytes: int = 0
    latency_ms: float = 0
    method: str = "daemon"          # "daemon" or "fallback"
    cached_state: bool = False
    error: Optional[str] = None


@dataclass(frozen=True)
class DaemonHealth:
    """Health status from the daemon /health endpoint."""
    connected: bool = False
    uptime_ms: int = 0
    captures_count: int = 0
    avg_latency_ms: float = 0
    p95_latency_ms: float = 0
    reconnect_count: int = 0
    current_symbol: Optional[str] = None
    current_timeframe: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# CLIENT
# ═══════════════════════════════════════════════════════════════

class PythonCaptureClient:
    """
    Async HTTP client adapter for the CaptureDaemon.

    Property 4: On daemon unavailability, transparently falls back to
    legacy subprocess mode via MCPClient._run().
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ):
        self._host = host or config.CAPTURE_DAEMON_HOST
        self._port = port or config.CAPTURE_DAEMON_PORT
        self._base_url = f"http://{self._host}:{self._port}"
        self._fallback_mode = False
        self._daemon_available: Optional[bool] = None
        self._last_check_time: float = 0
        self._check_cache_ttl: float = 5.0  # seconds

    @property
    def fallback_mode(self) -> bool:
        return self._fallback_mode

    # ── Core API ──────────────────────────────────────────────────────────────

    async def capture_screenshot(
        self,
        symbol: str = "active",
        timeframe: str = "D",
        region: str = "chart",
        crop: bool = True,
        save_path: Optional[Path] = None,
    ) -> CaptureResult:
        """
        Capture a chart screenshot via daemon HTTP API.
        Falls back to subprocess mode if daemon is unreachable.
        """
        if not await self.is_daemon_available():
            return await self._fallback_capture(symbol, timeframe, region, crop, save_path)

        try:
            import aiohttp
            payload = {
                "symbol": symbol,
                "timeframe": timeframe,
                "region": region,
                "crop": crop,
                "skip_if_same": True,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._base_url}/capture",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    data = await resp.json()

            if not data.get("success"):
                logger.warning(f"Daemon capture failed: {data.get('error')}")
                return CaptureResult(
                    success=False,
                    error=data.get("error", "Unknown daemon error"),
                    latency_ms=data.get("latency_ms", 0),
                    method="daemon",
                )

            # Save base64 to disk if save_path provided and base64 available
            file_path = data.get("file_path")
            if save_path and data.get("base64"):
                import base64 as b64
                save_path.parent.mkdir(parents=True, exist_ok=True)
                img_data = b64.b64decode(data["base64"])
                save_path.write_bytes(img_data)
                file_path = str(save_path)

            self._fallback_mode = False
            return CaptureResult(
                success=True,
                file_path=file_path,
                base64=data.get("base64"),
                size_bytes=data.get("size_bytes", 0),
                latency_ms=data.get("latency_ms", 0),
                method="daemon",
                cached_state=data.get("cached_state", False),
            )

        except Exception as e:
            logger.warning(f"Daemon capture error ({e}), falling back to subprocess")
            self._daemon_available = False
            self._fallback_mode = True
            return await self._fallback_capture(symbol, timeframe, region, crop, save_path)

    async def set_symbol(self, symbol: str, timeframe: str = "D") -> bool:
        """Change chart symbol/timeframe via daemon."""
        if not await self.is_daemon_available():
            return await self._fallback_set_symbol(symbol, timeframe)

        try:
            import aiohttp
            payload = {"symbol": symbol, "timeframe": timeframe}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._base_url}/set-chart",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    data = await resp.json()
            return data.get("success", False)
        except Exception as e:
            logger.warning(f"Daemon set_symbol error ({e}), falling back")
            return await self._fallback_set_symbol(symbol, timeframe)

    async def batch_run(self, symbols: List[Dict[str, str]]) -> List[CaptureResult]:
        """
        Batch capture multiple symbols.
        Property 3: Result count === input count.
        """
        if not await self.is_daemon_available():
            return await self._fallback_batch(symbols)

        try:
            import aiohttp
            payload = {"symbols": symbols}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._base_url}/batch-capture",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    data = await resp.json()

            results = []
            for r in data.get("results", []):
                results.append(CaptureResult(
                    success=r.get("success", False),
                    file_path=r.get("file_path"),
                    base64=r.get("base64"),
                    size_bytes=r.get("size_bytes", 0),
                    latency_ms=r.get("latency_ms", 0),
                    method="daemon",
                    cached_state=r.get("cached_state", False),
                    error=r.get("error"),
                ))
            return results

        except Exception as e:
            logger.warning(f"Daemon batch error ({e}), falling back")
            return await self._fallback_batch(symbols)

    async def get_health(self) -> DaemonHealth:
        """Query daemon health endpoint."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._base_url}/health",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    data = await resp.json()

            return DaemonHealth(
                connected=data.get("connected", False),
                uptime_ms=data.get("uptime_ms", 0),
                captures_count=data.get("captures_count", 0),
                avg_latency_ms=data.get("avg_latency_ms", 0),
                p95_latency_ms=data.get("p95_latency_ms", 0),
                reconnect_count=data.get("reconnect_count", 0),
                current_symbol=data.get("current_symbol"),
                current_timeframe=data.get("current_timeframe"),
            )
        except Exception:
            return DaemonHealth(connected=False)

    async def is_daemon_available(self) -> bool:
        """
        Check if daemon is reachable (with 5s TTL cache).
        On success, reverts from fallback mode.
        """
        now = time.monotonic()
        if self._daemon_available is not None and (now - self._last_check_time) < self._check_cache_ttl:
            return self._daemon_available

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._base_url}/health",
                    timeout=aiohttp.ClientTimeout(total=3),
                ) as resp:
                    self._daemon_available = resp.status == 200
                    if self._daemon_available and self._fallback_mode:
                        logger.info("Capture daemon recovered — switching back from fallback mode")
                        self._fallback_mode = False
        except Exception:
            self._daemon_available = False

        self._last_check_time = now
        return self._daemon_available

    # ── Fallback (legacy subprocess) ──────────────────────────────────────────

    async def _fallback_capture(
        self,
        symbol: str,
        timeframe: str,
        region: str,
        crop: bool,
        save_path: Optional[Path],
    ) -> CaptureResult:
        """Fallback to MCPClient subprocess mode."""
        logger.info(f"Fallback capture: {symbol} @ {timeframe}")
        self._fallback_mode = True
        start = time.monotonic()

        try:
            from mcp_client import get_mcp_client
            mcp = get_mcp_client()
            path = await mcp.capture_screenshot(
                symbol=symbol,
                timeframe=timeframe,
                region=region,
                save_path=save_path,
                crop=crop,
            )
            latency = (time.monotonic() - start) * 1000

            if path and path.exists():
                return CaptureResult(
                    success=True,
                    file_path=str(path),
                    size_bytes=path.stat().st_size,
                    latency_ms=latency,
                    method="fallback",
                )
            return CaptureResult(
                success=False,
                error="Subprocess capture returned no file",
                latency_ms=latency,
                method="fallback",
            )
        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            return CaptureResult(
                success=False,
                error=str(e),
                latency_ms=latency,
                method="fallback",
            )

    async def _fallback_set_symbol(self, symbol: str, timeframe: str) -> bool:
        """Fallback symbol change via subprocess."""
        try:
            from mcp_client import get_mcp_client
            mcp = get_mcp_client()
            return await mcp.set_symbol(symbol, timeframe)
        except Exception as e:
            logger.warning(f"Fallback set_symbol failed: {e}")
            return False

    async def _fallback_batch(self, symbols: List[Dict[str, str]]) -> List[CaptureResult]:
        """Fallback batch via sequential subprocess calls."""
        results = []
        for entry in symbols:
            result = await self._fallback_capture(
                symbol=entry.get("symbol", "active"),
                timeframe=entry.get("timeframe", "D"),
                region=entry.get("region", "chart"),
                crop=True,
                save_path=None,
            )
            results.append(result)
        return results


# ═══════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════

_capture_client: Optional[PythonCaptureClient] = None


def get_capture_client() -> PythonCaptureClient:
    global _capture_client
    if _capture_client is None:
        _capture_client = PythonCaptureClient()
    return _capture_client
