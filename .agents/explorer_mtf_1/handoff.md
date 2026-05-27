# Handoff Report: MTF Nested Chart Inset Layouts Analysis

## 1. Observation
- The FastAPI `/api/vision/capture` endpoint is located in `nerves/workers/trading/main.py` (lines 1030-1144). It resolves the capture method and calls `capture_client.get_capture_client().capture_screenshot(...)` as a fallback.
- The rendering function `generate_chart_lw` in `nerves/workers/trading/utils/chart_generator_lw.py` executes a Playwright script targeting `nerves/workers/trading/static/chart_template.html` to generate high-fidelity charts.
- The local fallback engine `generate_chart_mpl` in `nerves/workers/trading/utils/chart_generator_mpl.py` uses `mplfinance`/`matplotlib` to render a single chart of the primary timeframe.

## 2. Logic Chain
- Adding MTF nested overlays requires supplying the HTML template with higher-timeframe data.
- Introducing `MTF_PARENT_MAP` will map timeframe inputs (e.g. `1h`) to their corresponding parent interval (e.g. `4h`).
- Executing candle fetching concurrently via `asyncio.gather` for both parent and child timeframes keeps chart capture latency low.
- Passing `parent_ohlcv` and `parent_timeframe` through `chart_payload` will allow the browser execution scope to dynamically build the glassmorphism inset card using lightweight-charts.
- Restricting the Matplotlib fallback to a single chart keeps the fallback path extremely robust and avoids complex multi-axis subplot configurations.

## 3. Caveats
- Playwright startup has a cold start cost; fetching two sets of candles concurrently mitigates some of this latency, but total API response time will still depend on exchange endpoint responsiveness.
- The SVG connector coordinates are estimated relative to the parent container bounding rect; adjustments may be needed depending on the user's specific browser window geometry configuration.

## 4. Conclusion
The MTF Nested Chart Inset Layout is highly feasible and can be cleanly implemented by modifying the data-loading step in `capture_client.py`, extending the viewport payload in `chart_generator_lw.py`, and updating the CSS/DOM configuration in `chart_template.html`.

## 5. Verification Method
- **Verification Command**:
  Verify the setup works by running unit tests for the capture client and chart generators:
  `pytest nerves/workers/trading/tests/unit/test_capture_client_routing.py`
  `pytest nerves/workers/trading/tests/unit/test_chart_generators.py`
- **Files to Inspect**:
  - `nerves/workers/trading/capture_client.py`
  - `nerves/workers/trading/utils/chart_generator_lw.py`
  - `nerves/workers/trading/static/chart_template.html`
  - `nerves/workers/trading/utils/chart_generator_mpl.py`
