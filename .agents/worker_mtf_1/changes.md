# Implementation Report — MTF Inset Layouts

## Modified Files and Summary of Changes

### 1. `nerves/workers/trading/capture_client.py`
- Implemented case-insensitive timeframe mapping from lower timeframe to parent timeframe:
  - `15m` / `15` -> `1H`
  - `1h` / `60` / `1H` -> `4H`
- Implemented concurrent data fetching for target and parent candles using `asyncio.gather` inside `_local_capture`.
- Propagated `parent_timeframe` and `parent_ohlcv` downstream to both lightweight-charts and matplotlib generators.

### 2. `nerves/workers/trading/static/chart_template.html`
- Implemented a `#parent-inset-container` container with modern glassmorphism styling (`#1e222d` background, `8px` border radius, `rgba(255,255,255,0.08)` border).
- Rendered an SVG arrow indicator (#2962ff) pointing from the inset container to the main chart area.
- Initiated a secondary Lightweight Charts instance inside the inset container to render parent candles when `parent_ohlcv` is present in the payload.

### 3. `nerves/workers/trading/utils/chart_generator_lw.py`
- Added optional parameters `parent_timeframe` and `parent_ohlcv` to `generate_chart_lw`.
- Included parent properties in the payload passed to the HTML template.

### 4. `nerves/workers/trading/utils/chart_generator_mpl.py`
- Updated the signature of `generate_chart_mpl` to support `parent_timeframe` and `parent_ohlcv`.
- Designed it to ignore these fields gracefully, ensuring fallback rendering completes successfully as a single chart without exceptions.

### 5. `nerves/workers/trading/tests/unit/test_mtf_nested.py`
- Created a robust test suite testing:
  - Case-insensitive timeframe mapping
  - Concurrent data fetching via `asyncio.gather`
  - Single timeframe capture paths (which skip parent fetching)
  - Matplotlib fallback resilience
  - API endpoint integration (`/api/vision/capture`)
