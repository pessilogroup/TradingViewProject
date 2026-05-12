"""
P6 — MCP Client
Wrapper gọi TradingView MCP CLI (tradingview-mcp) qua subprocess.
TradingView Desktop phải đang chạy với --remote-debugging-port=9222
"""
import json
import asyncio
import base64
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

import config

logger = logging.getLogger(__name__)

# Path to MCP CLI
_MCP_DIR = Path(__file__).parent.parent / "tradingview-mcp"
_MCP_CLI = _MCP_DIR / "src" / "cli" / "index.js"


@dataclass
class QuoteData:
    symbol: str
    close: float
    open: float
    high: float
    low: float
    volume: float
    change_pct: float


@dataclass
class StudyValues:
    sma50: Optional[float] = None
    sma150: Optional[float] = None
    sma200: Optional[float] = None
    volume_avg20: Optional[float] = None
    atr14: Optional[float] = None
    rs_line: Optional[float] = None
    high_52w: Optional[float] = None
    low_52w: Optional[float] = None


class MCPClient:
    """Async wrapper for TradingView MCP CLI."""

    def __init__(self):
        self.enabled = config.MCP_ENABLED
        self.cdp_port = config.MCP_CDP_PORT
        self.node_path = config.MCP_NODE_PATH or "node"
        self._connected: Optional[bool] = None

    async def _run(self, *args, timeout: int = 15) -> dict:
        """Run MCP CLI command and return parsed JSON."""
        if not _MCP_CLI.exists():
            raise RuntimeError(
                f"TradingView MCP not found at {_MCP_CLI}. "
                "Run: git submodule update --init tradingview-mcp && cd tradingview-mcp && npm install"
            )

        cmd = [self.node_path, str(_MCP_CLI)] + list(args) + ["--json"]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(_MCP_DIR),
                env={**__import__("os").environ, "TV_CDP_PORT": str(self.cdp_port)}
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            if proc.returncode != 0:
                err = stderr.decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"MCP CLI error: {err}")

            raw = stdout.decode("utf-8", errors="replace").strip()
            # CLI emits pretty-printed JSON; try the full payload first,
            # then fall back to scanning for a single-line JSON value.
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass
            for line in raw.split("\n"):
                line = line.strip()
                if line.startswith("{") or line.startswith("["):
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue
            raise RuntimeError(f"MCP CLI returned non-JSON output: {raw[:200]}")

        except asyncio.TimeoutError:
            raise RuntimeError(f"MCP CLI timeout after {timeout}s")

    # ── Health Check ──────────────────────────────────────────────────────────

    async def health_check(self) -> dict:
        """Check if TradingView Desktop is connected via CDP."""
        try:
            result = await self._run("status", timeout=5)
            self._connected = bool(result.get("cdp_connected") or result.get("connected"))
            return {
                "connected": self._connected,
                "cdp_port": self.cdp_port,
                "mcp_cli_found": _MCP_CLI.exists(),
                "detail": result
            }
        except Exception as e:
            self._connected = False
            return {
                "connected": False,
                "cdp_port": self.cdp_port,
                "mcp_cli_found": _MCP_CLI.exists(),
                "error": str(e)
            }

    # ── Market Data ───────────────────────────────────────────────────────────

    async def get_quote(self, symbol: str) -> QuoteData:
        """Get current price + OHLCV for a symbol."""
        await self._run("symbol", symbol)
        raw = await self._run("quote")

        return QuoteData(
            symbol=symbol,
            close=float(raw.get("close", 0)),
            open=float(raw.get("open", 0)),
            high=float(raw.get("high", 0)),
            low=float(raw.get("low", 0)),
            volume=float(raw.get("volume", 0)),
            change_pct=float(raw.get("change_percent", 0)),
        )

    async def get_ohlcv_summary(self, symbol: str, timeframe: str = "D") -> dict:
        """Get compact OHLCV stats (summary mode = 500B)."""
        await self._run("symbol", symbol)
        await self._run("timeframe", timeframe)
        return await self._run("ohlcv", "--summary")

    async def get_study_values(self, symbol: str, timeframe: str = "D") -> StudyValues:
        """
        Read indicator values from chart.
        Assumes Minervini indicators (SMA50/150/200, Volume MA) are added on chart.
        """
        await self._run("symbol", symbol)
        await self._run("timeframe", timeframe)
        raw = await self._run("values")

        # Parse indicator values — key names depend on what's on chart
        values = raw if isinstance(raw, dict) else {}
        indicators = values.get("indicators", {}) or values

        def _find(keys: list) -> Optional[float]:
            for k in keys:
                for ikey, ival in indicators.items():
                    if k.lower() in ikey.lower():
                        try:
                            return float(ival)
                        except (TypeError, ValueError):
                            pass
            return None

        return StudyValues(
            sma50=_find(["sma 50", "sma50", "ma 50", "ma50"]),
            sma150=_find(["sma 150", "sma150", "ma 150", "ma150"]),
            sma200=_find(["sma 200", "sma200", "ma 200", "ma200"]),
            volume_avg20=_find(["vol ma", "volume ma", "vol avg", "vma"]),
            atr14=_find(["atr", "average true range"]),
            high_52w=_find(["52w high", "52 week high", "yearly high"]),
            low_52w=_find(["52w low", "52 week low", "yearly low"]),
        )

    # ── Screenshot ────────────────────────────────────────────────────────────

    async def capture_screenshot(
        self,
        symbol: str = "active",
        timeframe: str = "D",
        region: str = "chart",
        save_path: Optional[Path] = None,
        active_only: bool = False
    ) -> Optional[Path]:
        """
        Capture chart screenshot.
        Returns path to saved PNG file, or None on failure.
        """
        try:
            if not active_only:
                if symbol != "active": await self._run("symbol", symbol)
                if timeframe != "active": await self._run("timeframe", timeframe)
            raw = await self._run("screenshot", "-r", region, timeout=20)

            # MCP returns base64 or file path
            if "base64" in raw:
                img_data = base64.b64decode(raw["base64"])
                if save_path is None:
                    save_path = Path(__file__).parent / "screenshots" / f"{symbol}_{timeframe}.png"
                save_path.parent.mkdir(parents=True, exist_ok=True)
                save_path.write_bytes(img_data)
                return save_path

            if "file_path" in raw:
                return Path(raw["file_path"])
                
            if "path" in raw:
                return Path(raw["path"])

        except Exception as e:
            logger.warning(f"Screenshot failed for {symbol}: {e}")
        return None

    # ── Chart Control ─────────────────────────────────────────────────────────

    async def set_symbol(self, symbol: str, timeframe: str = "D") -> bool:
        """Switch chart to symbol + timeframe."""
        try:
            await self._run("symbol", symbol)
            await self._run("timeframe", timeframe)
            return True
        except Exception as e:
            logger.warning(f"set_symbol failed: {e}")
            return False

    async def batch_run(self, symbols: list[str], timeframe: str = "D") -> list[dict]:
        """
        Run quote + study_values for each symbol sequentially.
        Returns list of raw data dicts.
        """
        results = []
        for sym in symbols:
            try:
                quote = await self.get_quote(sym)
                studies = await self.get_study_values(sym, timeframe)
                ohlcv = await self.get_ohlcv_summary(sym, timeframe)

                results.append({
                    "symbol": sym,
                    "quote": quote,
                    "studies": studies,
                    "ohlcv_summary": ohlcv,
                    "error": None
                })
            except Exception as e:
                logger.warning(f"batch_run error for {sym}: {e}")
                results.append({"symbol": sym, "error": str(e)})

        return results


# Singleton
_mcp_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client
