# Analysis Report: Scanner Concurrency, Rate Limiting, and Scoring Engine

## 1. Executive Summary
This report analyzes the existing scoring engine (Trend Template & VCP) in `nerves/workers/trading/analysis.py` and the market data fetching mechanisms in `nerves/workers/trading/mcp_client.py`. 
Key findings show that:
1. **Trend Template and VCP Scores** are correctly computed via mathematical heuristics based on 8 Minervini criteria and 3 volatility contraction metrics.
2. **Subprocess/CDP Overhead**: The scanner launches at least 4 node subprocesses sequentially per symbol, opening and closing CDP connections to the active TradingView Desktop chart tab.
3. **State Contamination Hazard**: The active symbol and timeframe on TradingView Desktop is a stateful global parameter. Running concurrent scans will lead to race conditions where one symbol's quote matches another symbol's indicator study values.
4. **Lack of Rate Limiting**: There is no rate limit control, throttling, or retry handler, making the scanner vulnerable to 429 errors from TradingView's servers or browser loading timeouts.
5. **Robust Design Proposal**: We propose the `RobustScanner` architecture with an async mutex lock to serialize chart switching, a Token Bucket rate-limiter, an exponential back-off retry loop, and a 5-minute memory caching layer. We also explore CDP multiplexing using multiple browser tabs to scan 100+ active pairs concurrently.

---

## 2. Score Computation Engine
In `nerves/workers/trading/analysis.py`, the scanner computes two primary metrics: the **Trend Template Score** and the **VCP Result**.

### A. Minervini Trend Template (8 Criteria)
The function `score_trend_template` scores each symbol on a scale of **0 to 8** using the following rules:
1. **price_above_ma150_200**: Price > SMA150 AND Price > SMA200.
2. **ma150_above_ma200**: SMA150 > SMA200 (proves a long-term uptrend).
3. **ma200_trending_up**: SMA200 slope is positive (slope > 0, requiring a trend of at least 20 daily bars / 1 month).
4. **ma50_above_ma150_200**: SMA50 > SMA150 AND SMA50 > SMA200.
5. **price_above_ma50**: Price is above the 50-day simple moving average.
6. **above_52w_low_130pct**: Price >= 52-week low × 1.30 (price is at least 30% off its lows).
7. **within_25pct_of_52w_high**: Price >= 52-week high × 0.75 (price is within 25% of its yearly highs).
8. **rs_outperforming**: Relative Strength ratio vs S&P500/Benchmark is > 1.0.

#### Stage Classification
Based on the Trend Template score, assets are classified into market stages:
*   **Score >= 7**: `Stage 2 ⭐` (Minervini's prime accumulation and buying stage)
*   **Score >= 5**: `Stage 1/2 Transition` (Bottoming out, transitioning into Stage 2)
*   **Score >= 3**: `Stage 1 (Base)` (Sideways consolidation)
*   **Score < 3**: `Stage 3/4 (Avoid)` (Topping out or in a downtrend)

### B. Volatility Contraction Pattern (VCP)
The function `detect_vcp` identifies volatility contraction zones where "smart money" accumulates shares, drying up liquidity before a breakout:
1. **Volume Contraction** (`vol_contracting`): Current volume is less than 50% of its 20-period average (`volume / volume_avg20 < 0.5`).
2. **Range Contraction** (`range_contracting`): High-to-low price range is less than 50% of the ATR14 (`(high - low) / atr14 < 0.5`).
3. **Breakout Zone** (`near_high`): Price is within 10% of the 52-week high (`price >= high_52w * 0.90`).
4. **Volume Breakout** (`vol_breakout`): Vol ratio > 1.2 (for breakout confirmation).

*   **VCP is Detected** if and only if **both volume and price range are contracting** concurrently.
*   **Breakout Pivot Level**: Estimated as `round(high * 1.005, 2)` if VCP is detected.

---

## 3. Analysis of the Data-Fetching Pipeline
The current `scan_symbols` fetches data by invoking `mcp_client.batch_run(symbols)`. 

### A. Subprocess Overhead
`MCPClient._run` executes `node src/cli/index.js <args> --json` via `asyncio.create_subprocess_exec`. For a single symbol:
1. `_run("symbol", sym)` (switches active chart symbol)
2. `_run("quote")` (gets quote prices)
3. `_run("values")` (reads visible studies/indicators from data window)
4. `_run("ohlcv", "--summary")` (gets ATR14 and volume averages)

This represents **4 subprocess spawns per symbol**. For 100 symbols, this requires **400 node process executions**, creating immense CPU and file handle overhead.

### B. Stateful CDP Concurrency Hazards
`MCPClient` controls the GUI chart widget via CDP (`window.TradingViewApi._activeChartWidgetWV.value()`).
*   **Symbol switching is global**: Switching the symbol switches the single active chart view.
*   **Data contamination**: If multiple async tasks run `scan_symbols` or `set_symbol` in parallel, their commands will overlap. For example, Task 1 switches symbol to `BTCUSDT`, but before it can run `get_quote`, Task 2 switches the symbol to `ETHUSDT`. Task 1 then reads the quote and indicators of `ETHUSDT` but records it under the symbol `BTCUSDT`.
*   **Lack of locks**: There is no synchronization lock protecting access to the `MCPClient` or its underlying CDP instance.

### C. Rate Limits and Waiting Time
The TradingView Desktop chart must download historical data whenever a symbol is switched.
*   `waitForChartReady` polls the DOM every 200ms to ensure the loader spinner is gone, the header matches the target symbol, and the bar count is stable for at least 400ms.
*   This introduces a minimum delay of **400ms–1000ms+ per symbol**.
*   **Network Rate Limits**: Switching symbols rapidly causes TradingView Desktop to send dozens of WebSocket requests to TradingView servers. TradingView's cloud backend will eventually throttle the client (silent data load failure or empty charts), leading to 10s timeouts in `waitForChartReady`.

---

## 4. Proposed Robust Concurrency Queue & Rate Limiter Design

To support scanning 100+ active pairs concurrently without rate limits or state contamination, we propose the following design:

### 1. Persistent HTTP Daemon Communication
Eliminate subprocess overhead by routing all data queries to the existing `CaptureDaemon` (Node.js Express server) or extending it to support data queries (`/quote`, `/study-values`, `/ohlcv`) alongside `/capture`. The daemon maintains a long-lived CDP session.

### 2. Chart Access Serialization (Mutex Lock)
Since the TV Desktop active chart is a single shared resource, we must use an `asyncio.Lock` to ensure only one symbol is switched and queried at any time.

### 3. Token Bucket Rate Limiter
Throttle chart switching to a safe rate (e.g., 1 symbol switch per 1.2 seconds) to prevent TradingView servers from rate-limiting the desktop application.

### 4. Exponential Back-off on 429 or Timeout
If a symbol switch fails, the loader hangs, or a network request fails, catch the error, release the lock, and retry with exponential back-off (`delay * 2`).

### 5. Multi-Tab CDP Multiplexing (For True Concurrency)
Instead of a single active chart, we can open multiple tabs in TradingView Desktop (CDP supports multiple page targets). By allocating a pool of tabs (e.g., 5 tabs), we can scan 5 symbols concurrently, each having its own lock.

### Implementation Architecture (Proposed Python Class)

```python
import asyncio
import time
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class TokenBucketLimiter:
    """Async Token Bucket rate limiter to throttle requests."""
    def __init__(self, rate: float, capacity: float):
        self.rate = rate          # Tokens added per second
        self.capacity = capacity  # Maximum burst capacity
        self.tokens = capacity
        self.last_update = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0):
        async with self._lock:
            while True:
                now = time.time()
                elapsed = now - self.last_update
                self.last_update = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return
                
                wait_time = (tokens - self.tokens) / self.rate
                await asyncio.sleep(wait_time)

class RobustScanner:
    """
    Queue-based scanner that serializes access to the stateful TradingView Desktop chart,
    applies rate limiting, caching, and handles rate-limits with back-off.
    """
    def __init__(self, mcp_client, cache_ttl_seconds: int = 300):
        self.mcp = mcp_client
        self.lock = asyncio.Lock()  # Prevents state contamination
        self.limiter = TokenBucketLimiter(rate=0.8, capacity=2.0)  # Throttles symbol switching
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = cache_ttl_seconds
        
        # Exponential back-off config
        self.base_delay = 1.5
        self.backoff_factor = 2.0
        self.max_retries = 3

    def _get_cached_result(self, symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        key = f"{symbol}_{timeframe}"
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry["timestamp"] < self.cache_ttl:
                logger.debug(f"Cache hit for {key}")
                return entry["data"]
        return None

    def _set_cached_result(self, symbol: str, timeframe: str, data: Dict[str, Any]):
        key = f"{symbol}_{timeframe}"
        self.cache[key] = {
            "timestamp": time.time(),
            "data": data
        }

    async def scan_single_symbol(self, symbol: str, timeframe: str = "D") -> Dict[str, Any]:
        # 1. Check local cache
        cached = self._get_cached_result(symbol, timeframe)
        if cached:
            return cached

        # 2. Acquire serialization lock to switch chart
        async with self.lock:
            retries = 0
            current_delay = self.base_delay

            while retries <= self.max_retries:
                try:
                    # Rate limit symbol switches to avoid TV server block (429)
                    await self.limiter.acquire(1.0)
                    
                    # Switch chart symbol and timeframe
                    # set_symbol blocks until waitForChartReady confirms DOM stability
                    success = await self.mcp.set_symbol(symbol, timeframe)
                    if not success:
                        raise RuntimeError("TradingView chart load timeout or incorrect symbol name")

                    # Fetch quote + indicators + ohlcv within the locked session
                    quote = await self.mcp.get_quote(symbol)
                    studies = await self.mcp.get_study_values(symbol, timeframe)
                    ohlcv = await self.mcp.get_ohlcv_summary(symbol, timeframe)

                    result = {
                        "symbol": symbol,
                        "quote": quote,
                        "studies": studies,
                        "ohlcv_summary": ohlcv,
                        "error": None
                    }
                    self._set_cached_result(symbol, timeframe, result)
                    return result

                except Exception as e:
                    logger.warning(f"Scan error for {symbol} (Attempt {retries+1}/{self.max_retries+1}): {e}")
                    retries += 1
                    if retries > self.max_retries:
                        return {"symbol": symbol, "error": f"Failed after max retries: {str(e)}"}
                    
                    # Exponential back-off delay before releasing lock or retrying
                    await asyncio.sleep(current_delay)
                    current_delay *= self.backoff_factor

    async def scan_batch(self, symbols: List[str], timeframe: str = "D") -> List[Dict[str, Any]]:
        """Scans multiple symbols. Lock ensures they run sequentially without state collision."""
        tasks = [self.scan_single_symbol(sym, timeframe) for sym in symbols]
        return await asyncio.gather(*tasks)
```

---

## 5. Dynamic Symbol Scoring (Weex, Binance, Bybit)
To scan dynamic symbols from multiple exchanges:

1.  **TV-Compatible Formatting**: Dynamic symbols must be converted into the standard TradingView format.
    *   **Binance Spot/Futures**: `BINANCE:BTCUSDT` or `BINANCE:BTCUSDT.P`
    *   **Bybit Spot/Futures**: `BYBIT:BTCUSDT` or `BYBIT:BTCUSDT.P`
    *   **Weex**: If Weex is supported on TradingView, use the corresponding exchange prefix (e.g. `WEEX:BTCUSDT`). If not natively supported, the system maps the ticker to a correlated major feed (e.g. `BINANCE:BTCUSDT`) to compute general Trend Template / VCP scores, which are identical across feeds due to arbitrage.
2.  **Dynamic Chart Switch**: The scanner passes the formatted exchange ticker to `chart_set_symbol`.
3.  **Automatic Indicator Updates**: Once TradingView Desktop loads the chart, the indicators (SMA, Vol MA, ATR) adapt to the new ticker data.
4.  **Flexible Scoring**: The `MCPClient` retrieves study values from the data window, passing them to `score_trend_template` and `detect_vcp`. This ensures scores are computed accurately regardless of the underlying exchange.
