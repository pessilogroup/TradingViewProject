# Handoff Report - Scanner Concurrency & Rate Limiting Analysis

## 1. Observation
*   **Trend Template Scorer Location**: `nerves/workers/trading/analysis.py` (Lines 42-133) implements `score_trend_template(price, sma50, sma150, sma200, high_52w, low_52w, sma200_slope=None, rs_ratio=None)` returning a score between 0 and 8 based on 8 Minervini criteria.
*   **VCP Detector Location**: `nerves/workers/trading/analysis.py` (Lines 136-185) implements `detect_vcp(price, high, low, volume, volume_avg20, atr14, high_52w)` returning `VCPResult` where contraction is detected if `volume_ratio < 0.5` and `range_ratio < 0.5`.
*   **Stateful Subprocess Executions**: In `nerves/workers/trading/mcp_client.py`, the client runs MCP commands via subprocess:
    ```python
    # nerves/workers/trading/mcp_client.py (Lines 67-73)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(_MCP_DIR),
        env={**os.environ, "TV_CDP_PORT": str(self.cdp_port)}
    )
    ```
*   **Sequential Data Fetching**: `nerves/workers/trading/mcp_client.py` loops sequentially across symbols without locks or rate limiting:
    ```python
    # nerves/workers/trading/mcp_client.py (Lines 324-329)
    for sym in symbols:
        try:
            quote = await self.get_quote(sym)
            studies = await self.get_study_values(sym, timeframe)
            ohlcv = await self.get_ohlcv_summary(sym, timeframe)
    ```
*   **Chart Symbol Switch**: `tradingview-mcp/src/core/chart.js` (Line 46) executes a global chart change on the active widget:
    ```javascript
    chart.setSymbol(safeString(symbol), {});
    ```
*   **DOM Polling Wait**: `tradingview-mcp/src/wait.js` (Lines 6-72) runs `waitForChartReady` which checks the DOM for loading spinner and bar count stability, taking a minimum of 400ms to 1000ms+ per switch.

---

## 2. Logic Chain
1.  **Shared Global State**: Because `setSymbol` in `tradingview-mcp/src/core/chart.js` modifies the single active chart view on TradingView Desktop, the active ticker is a global stateful resource.
2.  **Concurrency Race Conditions**: If multiple scan requests run concurrently without serialization, tasks will overlap. For example, Task A sets the symbol to `BTCUSDT` and awaits `get_quote`. Before `get_quote` is executed, Task B changes the chart symbol to `ETHUSDT`. Task A then reads study values for `ETHUSDT` and logs them under `BTCUSDT` (data contamination).
3.  **Process Overhead**: Since `mcp_client.py` calls the CLI tool via `asyncio.create_subprocess_exec` four times per symbol, scanning 100 symbols results in 400 subprocess spawns. This leads to high CPU utilization and potential OS process starvation.
4.  **Network Rate Limiting**: Switching symbols rapidly forces TradingView Desktop to execute heavy WebSocket queries to TradingView servers. Without throttling, this causes the TV servers to rate limit the client (silently throttling websocket data or returning HTTP 429), leading to timeouts in `waitForChartReady`.
5.  **Synchronization Mitigation**: To scan 100+ active pairs concurrently without errors, we must:
    *   Serialize chart switches using an `asyncio.Lock`.
    *   Throttling switching speed using a Token Bucket limiter (e.g. max 1 switch per 1.2 seconds).
    *   Handle timeouts/failures gracefully via exponential back-off and retry blocks.
    *   Reduce subprocess overhead by routing requests through the persistent `CaptureDaemon` HTTP API or multiplexing chart queries across multiple pages/tabs.

---

## 3. Caveats
*   The scanner assumes the user has configured the necessary indicators (SMA50, SMA150, SMA200, Volume MA, ATR14) on the active TradingView chart. If these indicators are missing or named differently, `get_study_values` will fail to extract them.
*   True concurrency (running scans in parallel) is physically limited by the number of open pages/tabs in the TradingView Desktop application. Without multi-tab orchestration, scans must execute sequentially under the lock.

---

## 4. Conclusion
The existing scanner lacks synchronization and rate limiting, causing concurrency race hazards and susceptibility to TV server blocks. A robust design has been drafted in `.agents/explorer_m1_2/analysis.md` incorporating:
1.  An `asyncio.Lock` to guarantee stateful serialization.
2.  A Token Bucket limiter to throttle symbol switches.
3.  An exponential back-off retry mechanism for 429/timeouts.
4.  Standardized mapping rules for dynamic exchange symbols (Bybit/Binance/Weex) to TV-compatible formats.

---

## 5. Verification Method
1.  **Verify Analysis File**: Read `.agents/explorer_m1_2/analysis.md` and confirm it exists with the complete scanner architecture and computations.
2.  **Simulate Concurrency Race Condition**: Execute concurrent requests to `/api/scan/watchlist` and verify if mixed-symbol logs or timeouts occur.
3.  **Test Suite Execution**: Ensure existing tests pass:
    ```powershell
    pytest nerves/workers/trading/tests/unit/test_ai_analyzer.py
    ```
