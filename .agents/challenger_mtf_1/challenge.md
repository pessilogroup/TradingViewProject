## Challenge Summary

**Overall risk assessment**: MEDIUM

The Multi-Timeframe (MTF) Nested Chart Inset layouts implementation has been adversarially verified. While the core functionality (rendering the parent timeframe chart inset and connecting indicators) works well in standard conditions and falls back correctly, we identified key logic weaknesses and performance bottlenecks under stress.

---

## Challenges

### [High] Challenge 1: Primary-Parent Fetch Coupling Vulnerability

- **Assumption challenged**: The system assumes both primary and parent timeframe data must be fetched successfully together in order to perform local rendering.
- **Attack scenario**: If the primary timeframe fetch succeeds but the parent timeframe fetch fails (due to exchange API rate limits, socket timeouts, or unsupported intervals on the exchange), the `asyncio.gather(...)` call inside `_local_capture` raises an exception and crashes the entire screenshot process.
- **Blast radius**: The user will get a total failure (no chart image generated at all) even though the primary timeframe data was retrieved successfully and could have been rendered.
- **Mitigation**: Fetch timeframes sequentially or wrap the parent timeframe fetch in a separate `try...except` block within `_local_capture`, allowing rendering to fallback gracefully to a single timeframe chart if the parent data is unavailable.

### [Medium] Challenge 2: Lack of Concurrency Control under Fallback Mode

- **Assumption challenged**: The client assumes concurrent requests to `capture_screenshot` under fallback mode (`lightweight-charts`) can be launched concurrently without resource constraints.
- **Attack scenario**: When `batch_run` is called in local fallback mode, it uses `asyncio.gather(*tasks)` to run all screenshot operations concurrently. Since `lightweight-charts` launches a headless Chromium browser instance via Playwright for each render, a large batch (e.g. 10+ concurrent requests) will spawn 10+ Chromium instances at the same time.
- **Blast radius**: CPU thrashing, high RAM usage, memory exhaustion, browser crashes, or timeouts under heavy load.
- **Mitigation**: Introduce a concurrency throttle (such as `asyncio.Semaphore(3)`) to limit the number of parallel Playwright browser instances active simultaneously.

### [Medium] Challenge 3: Silent Degradation of MTF Visuals in Matplotlib Fallback

- **Assumption challenged**: Matplotlib (`mplfinance`) serves as an identical fallback engine for lightweight charts.
- **Attack scenario**: When browser rendering fails (e.g., CDN unpkg is down, or playwright has driver issues), the system falls back to `mplfinance`. However, `chart_generator_mpl.py` does not implement any inset rendering or connector line drawings, despite accepting `parent_timeframe` and `parent_ohlcv` parameters.
- **Blast radius**: The resulting screenshot degrades silently into a single timeframe chart, losing all MTF context without raising errors or warnings to the user.
- **Mitigation**: Either implement basic inset axes plotting in Matplotlib, or clearly log/warn when MTF visual capabilities are omitted during fallback.

### [Low] Challenge 4: Latency Coupling

- **Assumption challenged**: The asynchronous gather will hide latency.
- **Attack scenario**: When fetching parent trend data, any latency or delay in parent timeframe resolution blocks the primary chart rendering.
- **Blast radius**: Increased capture latency. A fast-loading primary chart is held back by a slow parent timeframe query.
- **Mitigation**: Render the primary timeframe chart first, or cap parent timeframe query latency with a strict timeout constraint.

---

## Stress Test Results

- **Parent Fetch Failure** → Expect `success=False` for the capture request when target succeeds but parent fails. → Checked: **FAIL** (crashes whole capture, no fallback to single timeframe).
- **Parent Fetch Latency** → Expect target capture time to stretch to the parent fetch latency. → Checked: **PASS** (duration coupled as expected).
- **Matplotlib Fallback** → Mock playwright failure, expect fallback to Matplotlib. → Checked: **PASS** (falls back to matplotlib but silent loss of MTF inset confirmed).
- **Concurrent Load** → Launch multiple concurrent mocked renders. → Checked: **PASS** (async task planning works, but resource usage unbounded).

---

## Unchallenged Areas

- **CCXT exchange credentials and live API rates** — Mocked to ensure deterministic test execution.
- **Node.js Daemon capture route** — Tested the fallback local routing path only; live Node.js process load limits are out of scope.
