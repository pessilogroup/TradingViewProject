"""
P11 — PythonCaptureClient
Thin async HTTP adapter that communicates with the CaptureDaemon (Node.js).
Falls back to native local rendering (lightweight-charts or mplfinance) if daemon is unreachable.

Design ref: design.md § "PythonCaptureClient"
"""
import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Union
from pathlib import Path

import config

logger = logging.getLogger(__name__)

# Timeframe mapping from TradingView standard to exchange standard
TIMEFRAME_MAP = {
    "1": "1m",
    "5": "5m",
    "15": "15m",
    "30": "30m",
    "60": "1h",
    "240": "4h",
    "D": "1d",
    "d": "1d",
    "W": "1w",
    "w": "1w",
    "M": "1M",
    "m": "1M",
}

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
    """Result from a capture operation (daemon, lightweight-charts, or mplfinance)."""
    success: bool
    file_path: Optional[str] = None
    base64: Optional[str] = None
    size_bytes: int = 0
    latency_ms: float = 0
    method: str = "daemon"          # "daemon", "lightweight-charts", "mplfinance", or "fallback"
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
    Transparently falls back to local chart rendering (lightweight-charts / mplfinance)
    on daemon unavailability or when native rendering is configured.
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
        
        # In-memory OHLCV cache to prevent redundant exchange API queries
        self._ohlcv_cache: Dict[tuple, Dict[str, Any]] = {}
        self._ohlcv_cache_ttl: float = 300.0  # 5 minutes

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
        ohlcv_data: Optional[List[Any]] = None,
        drawings: Optional[List[Dict[str, Any]]] = None,
        strategy_table: Optional[Dict[str, Any]] = None,
        method: Optional[str] = None,
    ) -> CaptureResult:
        """
        Capture a chart screenshot. Resolves capture method hierarchically:
        1. Explicitly passed `method` parameter.
        2. Database settings table override (`CHART_CAPTURE_METHOD`).
        3. Environment configuration default (`config.CHART_CAPTURE_METHOD`).
        
        If 'daemon' is resolved but unavailable, seamlessly falls back to 
        local native rendering.
        """
        start_time = time.monotonic()
        
        # Resolve capture method
        capture_method = method
        if not capture_method:
            try:
                import database
                capture_method = await database.get_setting("CHART_CAPTURE_METHOD")
            except Exception:
                pass
        if not capture_method:
            capture_method = config.CHART_CAPTURE_METHOD
            
        capture_method = capture_method.lower() if capture_method else "daemon"

        # Route to daemon if selected and available
        if capture_method == "daemon":
            if await self.is_daemon_available():
                daemon_res = await self._daemon_capture(symbol, timeframe, region, crop, save_path)
                if daemon_res.success:
                    return daemon_res
                else:
                    logger.warning(f"Daemon capture failed: {daemon_res.error}. Falling back to native local rendering...")
            else:
                logger.info("Daemon is unavailable. Falling back to native local rendering...")
            
            # If daemon failed or is unavailable, fallback to local rendering:
            # Prefer lightweight-charts as a high-fidelity rendering, fallback to mplfinance if playwright fails
            capture_method = "lightweight-charts"

        # Execute local native rendering
        local_res = await self._local_capture(
            symbol=symbol,
            timeframe=timeframe,
            save_path=save_path,
            ohlcv_data=ohlcv_data,
            drawings=drawings,
            strategy_table=strategy_table,
            method=capture_method
        )
        
        latency = (time.monotonic() - start_time) * 1000
        local_res.latency_ms = latency
        return local_res

    async def set_symbol(self, symbol: str, timeframe: str = "D") -> bool:
        """Change chart symbol/timeframe via daemon. Stateless for local modes."""
        if not await self.is_daemon_available():
            # Local mode is stateless; symbol change is a no-op that succeeds transparently
            return True

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
            logger.warning(f"Daemon set_symbol error ({e}), local fallback bypass active")
            return True

    async def batch_run(self, symbols: List[Dict[str, str]]) -> List[CaptureResult]:
        """
        Batch capture multiple symbols. Runs concurrently if using local rendering.
        """
        if await self.is_daemon_available():
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
                logger.warning(f"Daemon batch capture error ({e}), falling back to local concurrent captures")

        # Concurrently process batch using local/fallback client
        tasks = []
        for entry in symbols:
            tasks.append(self.capture_screenshot(
                symbol=entry.get("symbol", "active"),
                timeframe=entry.get("timeframe", "D"),
                region=entry.get("region", "chart"),
                crop=True,
                save_path=None,
            ))
        return list(await asyncio.gather(*tasks))

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
        """Check if daemon is reachable (with 5s TTL cache)."""
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

    # ── Daemon Integration ──────────────────────────────────────────────────

    async def _daemon_capture(
        self,
        symbol: str,
        timeframe: str,
        region: str,
        crop: bool,
        save_path: Optional[Path],
    ) -> CaptureResult:
        """Perform screenshot capture via Node.js daemon endpoint."""
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
                return CaptureResult(
                    success=False,
                    error=data.get("error", "Unknown daemon error"),
                    latency_ms=data.get("latency_ms", 0),
                    method="daemon",
                )

            file_path = data.get("file_path")
            if save_path and data.get("base64"):
                import base64 as b64
                save_path.parent.mkdir(parents=True, exist_ok=True)
                img_data = b64.b64decode(data["base64"])
                save_path.write_bytes(img_data)
                file_path = str(save_path)

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
            return CaptureResult(
                success=False,
                error=str(e),
                method="daemon"
            )

    # ── Native Local Rendering (Offline / Fast Capture) ──────────────────────

    async def _local_capture(
        self,
        symbol: str,
        timeframe: str,
        save_path: Optional[Path],
        ohlcv_data: Optional[List[Any]],
        drawings: Optional[List[Dict[str, Any]]],
        strategy_table: Optional[Dict[str, Any]],
        method: str,
    ) -> CaptureResult:
        """Executes native rendering locally using lightweight-charts or mplfinance."""
        self._fallback_mode = True
        
        # 1. Fetch OHLCV data if not provided
        if not ohlcv_data:
            try:
                candles_count = config.CHART_CANDLES_COUNT
                ohlcv_data = await self._get_ohlcv_data(symbol, timeframe, candles_count)
            except Exception as e:
                logger.error(f"Cannot perform local rendering: failed to retrieve OHLCV: {e}")
                return CaptureResult(
                    success=False,
                    error=f"OHLCV data retrieval failed: {e}",
                    method=method
                )

        # 2. Render via Lightweight Charts (Playwright)
        if method == "lightweight-charts":
            try:
                from utils.chart_generator_lw import generate_chart_lw
                img_path = await generate_chart_lw(
                    symbol=symbol,
                    timeframe=timeframe,
                    ohlcv_data=ohlcv_data,
                    drawings=drawings,
                    strategy_table=strategy_table,
                    save_path=save_path
                )
                
                size = img_path.stat().st_size
                import base64
                base64_str = base64.b64encode(img_path.read_bytes()).decode('utf-8')
                
                return CaptureResult(
                    success=True,
                    file_path=str(img_path),
                    base64=base64_str,
                    size_bytes=size,
                    method="lightweight-charts"
                )
            except Exception as e:
                logger.warning(f"lightweight-charts rendering failed ({e}). Falling back to mplfinance...")
                method = "mplfinance"  # Fallback to secondary line of defense

        # 3. Render via Matplotlib / mplfinance
        if method == "mplfinance":
            try:
                from utils.chart_generator_mpl import generate_chart_mpl
                loop = asyncio.get_event_loop()
                # Run CPU-bound matplotlib render in executor
                img_path = await loop.run_in_executor(
                    None,
                    lambda: generate_chart_mpl(
                        symbol=symbol,
                        timeframe=timeframe,
                        ohlcv_data=ohlcv_data,
                        drawings=drawings,
                        strategy_table=strategy_table,
                        save_path=save_path
                    )
                )
                
                size = img_path.stat().st_size
                import base64
                base64_str = base64.b64encode(img_path.read_bytes()).decode('utf-8')
                
                return CaptureResult(
                    success=True,
                    file_path=str(img_path),
                    base64=base64_str,
                    size_bytes=size,
                    method="mplfinance"
                )
            except Exception as e:
                logger.error(f"mplfinance rendering failed: {e}")
                return CaptureResult(
                    success=False,
                    error=f"Local native rendering failed: {e}",
                    method="mplfinance"
                )

        return CaptureResult(
            success=False,
            error=f"Unknown capture method: {method}",
            method=method
        )

    # ── OHLCV Data Fetcher & Cache ───────────────────────────────────────────

    async def _get_ohlcv_data(self, symbol: str, timeframe: str, limit: int) -> List[Any]:
        """Gets OHLCV data from cache or from external public exchange endpoints."""
        now = time.time()
        cache_key = (symbol, timeframe)
        
        # Check cache
        if cache_key in self._ohlcv_cache:
            entry = self._ohlcv_cache[cache_key]
            if now - entry["timestamp"] < self._ohlcv_cache_ttl:
                return entry["data"]

        # Fetch from exchange
        ohlcv = await self._fetch_ohlcv_from_exchange(symbol, timeframe, limit)
        
        # Save cache
        self._ohlcv_cache[cache_key] = {"timestamp": now, "data": ohlcv}
        return ohlcv

    async def _fetch_ohlcv_from_exchange(self, symbol: str, timeframe: str, limit: int) -> List[Any]:
        """Fetch OHLCV klines from configured exchange using CCXT or direct public REST APIs."""
        interval = TIMEFRAME_MAP.get(timeframe, timeframe)
        exchange_name = config.DEFAULT_EXCHANGE.lower()
        if symbol.endswith("_UMCBL") or exchange_name == "weex":
            exchange_name = "weex"


        # Try CCXT if enabled
        if config.CHART_CCXT_FALLBACK:
            try:
                import ccxt
                exchange_class = getattr(ccxt, exchange_name, None)
                if exchange_class:
                    ccxt_symbol = symbol
                    if '/' not in symbol:
                        if symbol.endswith("USDT"):
                            ccxt_symbol = symbol[:-4] + "/USDT"
                        elif symbol.endswith("BUSD"):
                            ccxt_symbol = symbol[:-4] + "/BUSD"
                        elif symbol.endswith("BTC"):
                            ccxt_symbol = symbol[:-3] + "/BTC"

                    # Fetch in executor to prevent event loop blocking
                    loop = asyncio.get_event_loop()
                    def sync_fetch():
                        inst = exchange_class({'enableRateLimit': True})
                        try:
                            return inst.fetch_ohlcv(ccxt_symbol, interval, limit=limit)
                        finally:
                            try:
                                inst.close()
                            except:
                                pass
                                
                    ohlcv = await loop.run_in_executor(None, sync_fetch)
                    if ohlcv:
                        return ohlcv
            except Exception as e:
                logger.warning(f"CCXT OHLCV fetch failed: {e}. Falling back to public REST APIs...")

        # Fallback to direct public HTTP requests
        try:
            import aiohttp
            if exchange_name == "bybit":
                url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval={interval}&limit={limit}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=10) as resp:
                        res = await resp.json()
                        if res.get("retCode") == 0:
                            list_data = res["result"]["list"]
                            ohlcv = []
                            for c in list_data:
                                ohlcv.append([
                                    int(c[0]),
                                    float(c[1]),
                                    float(c[2]),
                                    float(c[3]),
                                    float(c[4]),
                                    float(c[5])
                                ])
                            ohlcv.reverse()  # ascending chronological order
                            return ohlcv
            elif exchange_name == "weex":
                # Normalize symbol: e.g. BTCUSDT_UMCBL or BTC/USDT -> cmt_btcusdt
                clean_symbol = symbol.upper().replace("/", "").replace("-", "").replace("_UMCBL", "").lower()
                weex_symbol = f"cmt_{clean_symbol}"
                
                # Granularity: Weex contract V2 uses e.g. 1m, 5m, 15m, 30m, 1h, 4h, 12h, 1d, 1w
                url = f"https://api-contract.weex.com/capi/v2/market/candles?symbol={weex_symbol}&granularity={interval}&limit={limit}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=10) as resp:
                        res = await resp.json()
                        if isinstance(res, list):
                            ohlcv = []
                            for c in res:
                                ohlcv.append([
                                    int(c[0]),
                                    float(c[1]),
                                    float(c[2]),
                                    float(c[3]),
                                    float(c[4]),
                                    float(c[5])
                                ])
                            ohlcv.sort(key=lambda x: x[0])  # ascending chronological order
                            return ohlcv
                        else:
                            raise ValueError(f"Weex response is not list: {res}")
            else:
                # Default to Binance
                # Normalize interval mapping for binance (e.g. 1d, 1w)
                url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=10) as resp:
                        list_data = await resp.json()
                        if not isinstance(list_data, list):
                            raise ValueError(f"Binance response is not list: {list_data}")
                        ohlcv = []
                        for c in list_data:
                            ohlcv.append([
                                int(c[0]),
                                float(c[1]),
                                float(c[2]),
                                float(c[3]),
                                float(c[4]),
                                float(c[5])
                            ])
                        return ohlcv
        except Exception as e:
            logger.error(f"Direct REST API OHLCV fetch failed: {e}")
            raise


# ═══════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════

_capture_client: Optional[PythonCaptureClient] = None


def get_capture_client() -> PythonCaptureClient:
    global _capture_client
    if _capture_client is None:
        _capture_client = PythonCaptureClient()
    return _capture_client
