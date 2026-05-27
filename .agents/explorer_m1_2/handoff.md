# Handoff Report - explorer_m1_2

This report summarizes findings and evidence for the investigation of active symbol and study value extraction from the TradingView Desktop interface.

---

## 1. Observation

We observed and inspected the following specific code locations:

### A. `tradingview-mcp/src/connection.js`
- **Line 12**: Defines the global JS API path for active chart widget:
  ```javascript
  chartApi: 'window.TradingViewApi._activeChartWidgetWV.value()',
  ```
- **Line 18**: Defines main series bars:
  ```javascript
  mainSeriesBars: 'window.TradingViewApi._activeChartWidgetWV.value()._chartWidget.model().mainSeries().bars()',
  ```
- **Line 106-121**: Defines the `evaluate` function:
  ```javascript
  export async function evaluate(expression, opts = {}) {
    const c = await getClient();
    const result = await c.Runtime.evaluate({
      expression,
      returnByValue: true,
      awaitPromise: opts.awaitPromise ?? false,
      ...opts,
    });
    ...
  ```

### B. `tradingview-mcp/src/core/indicators.js`
- **Line 6**: Sets base widget API path:
  ```javascript
  const CHART_API = 'window.TradingViewApi._activeChartWidgetWV.value()';
  ```
- **Lines 17-21**: Gets study inputs dynamically via CDP:
  ```javascript
  const result = await evaluate(`
    (function() {
      var chart = ${CHART_API};
      var study = chart.getStudyById(${safeString(entity_id)});
  ```

### C. `tradingview-mcp/src/core/data.js`
- **Lines 245-278**: Defines `getQuote` which retrieves symbol, price, volume, and fallback selectors:
  ```javascript
  export async function getQuote({ symbol } = {}) {
    const data = await evaluate(`
      (function() {
        var api = ${CHART_API};
        var sym = ${safeString(symbol || '')};
        if (!sym) { try { sym = api.symbol(); } catch(e) {} }
        if (!sym) { try { sym = api.symbolExt().symbol; } catch(e) {} }
        ...
        try {
          var bidEl = document.querySelector('[class*="bid"] [class*="price"], [class*="dom-"] [class*="bid"]');
          var askEl = document.querySelector('[class*="ask"] [class*="price"], [class*="dom-"] [class*="ask"]');
          if (bidEl) quote.bid = parseFloat(bidEl.textContent.replace(/[^0-9.\\-]/g, ''));
          if (askEl) quote.ask = parseFloat(askEl.textContent.replace(/[^0-9.\\-]/g, ''));
        } catch(e) {}
  ```
- **Lines 324-358**: Defines `getStudyValues()` which queries studies from `dataWindowView()`:
  ```javascript
  export async function getStudyValues() {
    const data = await evaluate(`
      (function() {
        var chart = window.TradingViewApi._activeChartWidgetWV.value()._chartWidget;
        var model = chart.model();
        var sources = model.model().dataSources();
        var results = [];
        for (var si = 0; si < sources.length; si++) {
          var s = sources[si];
          if (!s.metaInfo) continue;
          try {
            var meta = s.metaInfo();
            var name = meta.description || meta.shortDescription || '';
            if (!name) continue;
            var values = {};
            try {
              var dwv = s.dataWindowView();
              if (dwv) {
                var items = dwv.items();
                if (items) {
                  for (var i = 0; i < items.length; i++) {
                    var item = items[i];
                    if (item._value && item._value !== '∅' && item._title) values[item._title] = item._value;
                  }
                }
              }
            } catch(e) {}
            if (Object.keys(values).length > 0) results.push({ name: name, values: values });
          ...
  ```

### D. `tradingview-mcp/src/wait.js`
- **Line 28-30**: Fallback DOM selector queries:
  ```javascript
  var symbolEl = document.querySelector('[data-name="legend-source-title"]')
    || document.querySelector('[class*="title"] [class*="apply-common-tooltip"]');
  var currentSymbol = symbolEl ? symbolEl.textContent.trim() : '';
  ```

### E. `nerves/workers/trading/mcp_client.py`
- **Lines 144-175**: Defines python `get_study_values` parsing study metrics:
  ```python
  async def get_study_values(self, symbol: str, timeframe: str = "D") -> StudyValues:
      ...
      raw = await self._run("values")
      values = raw if isinstance(raw, dict) else {}
      indicators = values.get("indicators", {}) or values
      def _find(keys: list) -> Optional[float]:
          for k in keys:
              for ikey, ival in indicators.items():
                  if k.lower() in ikey.lower():
                      ...
      return StudyValues(
          sma50=_find(["sma 50", "sma50", "ma 50", "ma50"]),
          ...
  ```
- **Line 237-238**: Fallback ticker initialization in screenshot capture:
  ```python
  target_symbol = symbol if symbol != "active" else "BTCUSDT"
  ```

---

## 2. Logic Chain

1. **JS-based Extraction**: `connection.js` exports evaluating expressions in CDP targets. `data.js` leverages this to query `TradingViewApi._activeChartWidgetWV.value()` to retrieve `symbol()`, `resolution()`, and `getStudyValues()`.
2. **DOM-based Extraction**: Under `wait.js`, `getQuote` in `data.js`, and general TV layouts, elements like `[data-name="legend-source-title"]`, and classes containing `bid` or `ask` or `last-` are queried with `document.querySelector` to find tickers and bid/ask/last prices when the API isn't used.
3. **Fuzzy Study Mapping**: `mcp_client.py` retrieves the indicators via a JSON list returned by `values` CLI command. It maps `StudyValues` fields (SMA50, SMA150, SMA200, ATR14) by filtering keys case-insensitively for matches like `sma 50`, `sma 150`, `sma 200`, `atr` or `average true range`.
4. **Fallback Tickering**: If DOM parsing/selection returns empty or fails, the capture daemon/screenshot client defaults to `"BTCUSDT"` or `"TAOUSDT"` as fallback tickers.

---

## 3. Caveats

- **DOM Instability**: CSS class names containing hashes or generic titles in TradingView Desktop can change with newer software versions, making direct JS API queries (`window.TradingViewApi`) much more stable than raw selector paths.
- **Visual Insets**: Matplotlib-based capture fallbacks will not render nested Multi-timeframe layout overlays if Playwright browser interaction fails, dropping back to a single timeframe plot.

---

## 4. Conclusion

The system reliably connects to the running TradingView Desktop instance over CDP on port 9222. Active symbol, timeframe, price, and study value arrays (specifically SMA50, SMA150, SMA200, volume average, and ATR14) are extracted via direct runtime JS queries in the Chrome DevTools session. DOM queries like `[data-name="legend-source-title"]` provide a secondary fallback mechanism, while `BTCUSDT`/`TAOUSDT` act as the ultimate default tickers if extraction completely fails.

---

## 5. Verification Method

- Run the E2E test suite to verify the mock webhook and ingestion pipeline:
  ```bash
  pytest nerves/workers/trading/tests/e2e/test_indicator_signals_feed_e2e.py
  ```
- Check the files:
  - `nerves/workers/trading/mcp_client.py` (lines 144-175) to verify study parsing logic.
  - `tradingview-mcp/src/core/data.js` (lines 324-358) to verify study value JS extraction.
