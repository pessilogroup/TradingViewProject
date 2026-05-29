# Analysis Report: MTF Nested Chart Inset Layout Design

This report details the current architecture of the screenshot capture engine, template rendering system, and fallback rendering mechanisms, and outlines a comprehensive design for introducing Multi-Timeframe (MTF) Nested Chart Inset Layouts.

---

## 1. Analysis of Current Architecture

### 1.1 `/api/vision/capture` Endpoint (`nerves/workers/trading/main.py`)
- **Route**: `POST /api/vision/capture`
- **Parameters**: `symbol` (default `"BTCUSDT"`), `timeframe` (default `"1h"`).
- **Execution Flow**:
  1. **CDP/MCP Screenshot Capture**: If `config.MCP_ENABLED` is `True`, it tries to call the desktop app via `mcp.capture_screenshot(symbol=sym, timeframe=tf)`.
  2. **Local Fallback**: If MCP is not available or fails, it imports `get_capture_client()` from `capture_client.py` and runs `client.capture_screenshot(symbol=sym, timeframe=tf, method="lightweight-charts")`.
  3. **Vision Analysis**: Performs AI visual analysis on the captured screenshot via `vision_module.analyze_chart_vision(...)`.
  4. **Persistence & Telegram**: Saves the capture and analysis metadata in the database (`database.insert_brief(...)`) and sends a notification message with the chart photo via Telegram.

### 1.2 Candle Fetching & Exchange Adapters (`nerves/workers/trading/capture_client.py`)
- **Method**: `_get_ohlcv_data(symbol, timeframe, limit)`
- **Caching**: Implements a simple in-memory cache `self._ohlcv_cache` with a TTL of 300 seconds (5 minutes) to avoid redundant requests.
- **Adapters Routing**:
  - The client resolves the primary exchange (defaulting to `config.DEFAULT_EXCHANGE` or `"weex"` if the symbol ends with `"_UMCBL"`).
  - Iterates through a prioritized list of exchanges (`[primary_exchange, "binance", "bybit", "weex"]`).
  - Tries direct fetching via `_fetch_raw_ohlcv(symbol, interval, limit, exchange)`:
    - First, attempts to use `ccxt` (if `config.CHART_CCXT_FALLBACK` is `True`).
    - If CCXT is disabled or fails, it falls back to raw HTTP requests to public REST APIs (Bybit, Weex contract API, or Binance Kline API).
  - **Weekly Fallback**: If requesting a weekly chart (`timeframe` is `W` or `1w`), it fetches daily candles (`1d`) and resamples them chronologically into weekly intervals starting on Mondays (`_resample_daily_to_weekly`).

### 1.3 HTML Template Rendering (`nerves/workers/trading/utils/chart_generator_lw.py`)
- **Playwright Setup**: Launch Chromium in headless mode, sets the viewport size to `1200x700` pixels.
- **Rendering Context**: Loads the template file located at `nerves/workers/trading/static/chart_template.html` using the absolute file URI.
- **Data Injection**: Passes the payload dynamically to the browser context:
  ```python
  chart_payload = {
      "symbol": symbol,
      "timeframe": timeframe,
      "ohlcv": ohlcv_data,
      "drawings": drawings or [],
      "strategy_table": strategy_table
  }
  await page.evaluate(f"window.renderChart({json.dumps(chart_payload)})")
  ```
- **Sync Sentinel**: Listens for `#chart-loaded` (success) or `#chart-error` (failure) elements to attach to the DOM before taking the screenshot.

### 1.4 Matplotlib Fallback Rendering (`nerves/workers/trading/utils/chart_generator_mpl.py`)
- **Triggers**: When Playwright fails or `CHART_CAPTURE_METHOD` resolves to `mplfinance`.
- **Implementation**: Runs a CPU-bound Matplotlib rendering task inside a thread pool (`loop.run_in_executor(None, ...)`) via `generate_chart_mpl`.
- **Styling**: Configures a dark theme mimicking TradingView using custom market colors (`up='#26a69a'`, `down='#ef5350'`) and grid lines (`gridcolor='#2a2e39'`).
- **Overlays**: Custom functions render EMA20/SMA50, support/resistance line drawings, and strategy table details.

---

## 2. Proposed MTF Inset Layout Design

To display a nested higher-timeframe chart overlay directly onto the primary chart, we design the following modifications:

### 2.1 Timeframe Mapping Definition
We define an explicit hierarchical mapping matching standard child intervals to their macro trend (parent) timeframes:
```python
# Mappings to define the parent timeframe for macro trend alignment context
MTF_PARENT_MAP = {
    "1m": "15m",
    "5m": "30m",
    "15m": "1h",
    "30m": "4h",
    "1h": "4h",
    "4h": "1d",
    "1d": "1w",
    # TV format normalization:
    "1": "15",
    "5": "30",
    "15": "60",
    "30": "240",
    "60": "240",
    "240": "D",
    "D": "W",
    "W": "M"
}
```

### 2.2 Concurrent Parent/Child Candle Fetching
In `capture_client.py` and `chart_generator_lw.py`, fetching parent candles should occur in parallel with child candles using `asyncio.gather` to keep latency low.

```python
parent_timeframe = MTF_PARENT_MAP.get(timeframe)
if parent_timeframe:
    # Concurrent fetch
    child_candles, parent_candles = await asyncio.gather(
        self._get_ohlcv_data(symbol, timeframe, limit),
        self._get_ohlcv_data(symbol, parent_timeframe, limit)
    )
else:
    child_candles = await self._get_ohlcv_data(symbol, timeframe, limit)
    parent_candles = None
```

### 2.3 Injecting Parent Data to HTML Payload
Extend the `chart_payload` dictionary in `chart_generator_lw.py` to forward parent chart details:
```python
chart_payload = {
    "symbol": symbol,
    "timeframe": timeframe,
    "ohlcv": ohlcv_data,
    "parent_timeframe": parent_timeframe,
    "parent_ohlcv": parent_candles,
    "drawings": drawings or [],
    "strategy_table": strategy_table
}
```

### 2.4 HTML/CSS Glassmorphism Overlay and SVG Arrow (`chart_template.html`)
To host the parent chart, we add a nested container styled with a premium frosted-glass design (backdrop-filter) and initialize a secondary Lightweight Chart instance inside it.

#### CSS Styling Addition:
```css
#parent-inset-container {
    position: absolute;
    bottom: 50px;
    right: 120px; /* Offset to clear the main price scale */
    width: 340px;
    height: 220px;
    background: rgba(30, 34, 45, 0.45);
    backdrop-filter: blur(12px) saturate(140%);
    -webkit-backdrop-filter: blur(12px) saturate(140%);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5);
    z-index: 105;
    padding: 8px;
    display: none; /* Shown dynamically if parent data exists */
}
#parent-inset-title {
    color: #ffffff;
    font-size: 10px;
    font-weight: bold;
    margin-bottom: 4px;
    opacity: 0.8;
}
#parent-inset-chart {
    width: 100%;
    height: 195px;
}
#svg-connector {
    position: absolute;
    pointer-events: none;
    z-index: 104;
    width: 100%;
    height: 100%;
    top: 0;
    left: 0;
    display: none;
}
```

#### HTML Markup Structure:
```html
<svg id="svg-connector">
    <!-- SVG arrow path will be dynamically updated by Javascript to link parent & child elements -->
    <path id="connector-line" stroke="rgba(255, 255, 255, 0.3)" stroke-width="1.5" stroke-dasharray="4,4" fill="none" />
    <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(255, 255, 255, 0.4)" />
    </marker>
</svg>

<div id="parent-inset-container">
    <div id="parent-inset-title" id="parent-title-overlay">PARENT TREND [1D]</div>
    <div id="parent-inset-chart"></div>
</div>
```

#### Javascript Implementation inside `window.renderChart`:
```javascript
if (chartData.parent_ohlcv && chartData.parent_ohlcv.length > 0) {
    const parentContainer = document.getElementById('parent-inset-container');
    parentContainer.style.display = 'block';
    
    document.getElementById('parent-title-overlay').innerText = `PARENT TREND [${chartData.parent_timeframe}]`;
    
    const parentChart = LightweightCharts.createChart(document.getElementById('parent-inset-chart'), {
        width: 324,
        height: 190,
        layout: {
            background: { type: 'solid', color: 'transparent' }, // transparent to showcase glassmorphism
            textColor: '#b2b5be',
            fontSize: 10,
        },
        grid: {
            vertLines: { color: 'rgba(42, 46, 57, 0.3)' },
            horzLines: { color: 'rgba(42, 46, 57, 0.3)' },
        },
        rightPriceScale: {
            borderColor: 'rgba(42, 46, 57, 0.3)',
            autoScale: true,
        },
        timeScale: {
            borderColor: 'rgba(42, 46, 57, 0.3)',
            timeVisible: false,
        }
    });

    const parentSeries = parentChart.addCandlestickSeries({
        upColor: '#26a69a',
        downColor: '#ef5350',
        borderVisible: false,
    });
    
    // Parse and map parent OHLCV data
    const parentCandles = chartData.parent_ohlcv.map(c => {
        let t = Array.isArray(c) ? c[0] : (c.time || c.timestamp);
        return {
            time: typeof t === 'number' ? t / 1000 : t,
            open: parseFloat(Array.isArray(c) ? c[1] : c.open),
            high: parseFloat(Array.isArray(c) ? c[2] : c.high),
            low: parseFloat(Array.isArray(c) ? c[3] : c.low),
            close: parseFloat(Array.isArray(c) ? c[4] : c.close),
        };
    });
    
    parentCandles.sort((a, b) => a.time - b.time);
    parentSeries.setData(parentCandles);
    parentChart.timeScale().fitContent();

    // Render connection SVG lines (optional styling)
    const connector = document.getElementById('svg-connector');
    connector.style.display = 'block';
    const line = document.getElementById('connector-line');
    
    // Target coordinate: point from the left edge of parent container 
    // to a relative region on the main time scale or right pane
    const rect = parentContainer.getBoundingClientRect();
    const startX = rect.left;
    const startY = rect.top + rect.height / 2;
    const endX = startX - 60;
    const endY = startY - 40;
    
    line.setAttribute('d', `M ${startX} ${startY} Q ${startX - 30} ${startY} ${endX} ${endY}`);
    line.setAttribute('marker-end', 'url(#arrow)');
}
```

### 2.5 Ensuring Matplotlib Fallback Renders a Clean Single Chart
- To ensure the secondary Matplotlib path remains highly readable, standardizing the fallback to render only the *primary child timeframe* is highly recommended. 
- Drawing sub-charts or nested frames inside Matplotlib under headless script execution is highly prone to scale collisions, overlapping axes, and clipping errors.
- If necessary, the fallback `generate_chart_mpl` can append a clear subtitle block indicating macro alignment verdict text (e.g. `"Parent Timeframe [1D] - Bullish Mode"`) inside the existing strategy specs box, instead of attempting to draw nested subplots.
