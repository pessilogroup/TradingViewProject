# TradingView Study Extractor Investigation Report

This report presents findings from the investigation of symbol and study values extraction (including SMA50, SMA150, SMA200, and ATR14) from the TradingView Desktop interface using the Chrome DevTools Protocol (CDP) and the `tradingview-mcp` codebase.

---

## 1. Examination of `tradingview-mcp` Code

The `tradingview-mcp` package acts as a bridge connecting an automation client to the running TradingView Desktop instance. 

### `tradingview-mcp/src/connection.js`
- **CDP Connection**: Establishes a session with the local Chrome DevTools Protocol (CDP) server running on port `9222`.
- **Target Discovery**: Scans target pages to find an active TradingView chart using the regular expressions `/tradingview\.com\/chart/i` and `/tradingview/i` via the endpoint `http://localhost:9222/json/list`.
- **JS Evaluation**: Evaluates JS code snippets in the chart window context using `CDP.Runtime.evaluate()` with `returnByValue: true`.
- **Key API Path Mapping**:
  - `chartApi`: `'window.TradingViewApi._activeChartWidgetWV.value()'`
  - `mainSeriesBars`: `'window.TradingViewApi._activeChartWidgetWV.value()._chartWidget.model().mainSeries().bars()'`

### `tradingview-mcp/src/core/indicators.js`
- **Study Interaction**: Interacts with studies on the chart.
- **Set Inputs**: Features `setInputs({ entity_id, inputs })` which uses JavaScript to locate a study via `chart.getStudyById(entity_id)` and update its inputs using `.getInputValues()` and `.setInputValues()`.
- **Toggle Visibility**: Features `toggleVisibility({ entity_id, visible })` which calls `.setVisible(visible)` on the study object.

### `tradingview-mcp/src/cli/commands/indicator.js`
- **CLI Registration**: Hooks subcommands to the `router` under the `indicator` command group:
  - `add`: Calls `chartCore.manageIndicator` with action `add`.
  - `remove`: Calls `chartCore.manageIndicator` with action `remove`.
  - `toggle`: Calls `indCore.toggleVisibility`.
  - `set`: Calls `indCore.setInputs`.
  - `get`: Calls `dataCore.getIndicator` to fetch current configuration and values.

---

## 2. DOM Selectors and JS Expressions for Extraction

To extract data directly from the active TradingView chart page, we can use either internal JS expressions evaluated via CDP (preferred for performance and accuracy) or query the HTML DOM selectors directly.

### A. JS Expressions (via CDP on the global window context)
- **Active Symbol Name**: 
  - `window.TradingViewApi._activeChartWidgetWV.value().symbol()` -> Returns a string containing the current exchange/symbol (e.g. `"BINANCE:BTCUSDT"`).
  - `window.TradingViewApi._activeChartWidgetWV.value().symbolExt().symbol` -> Returns only the symbol part (e.g., `"BTCUSDT"`).
- **Price (Latest Close)**:
  - `window.TradingViewApi._activeChartWidgetWV.value()._chartWidget.model().mainSeries().bars().valueAt(window.TradingViewApi._activeChartWidgetWV.value()._chartWidget.model().mainSeries().bars().lastIndex())[4]` -> Returns the closing price of the current bar (index `4` in the bar array).
- **Timeframe Interval**:
  - `window.TradingViewApi._activeChartWidgetWV.value().resolution()` -> Returns the timeframe/resolution string (e.g., `"D"`, `"1D"`, `"240"`, `"60"`, `"15"`).
- **Indicator Values (via Data Window View)**:
  - Iterating over `window.TradingViewApi._activeChartWidgetWV.value()._chartWidget.model().model().dataSources()` and retrieving values from the Data Window View:
    ```javascript
    (function() {
      var chart = window.TradingViewApi._activeChartWidgetWV.value()._chartWidget;
      var sources = chart.model().model().dataSources();
      var results = [];
      for (var si = 0; si < sources.length; si++) {
        var s = sources[si];
        if (!s.metaInfo) continue;
        try {
          var meta = s.metaInfo();
          var name = meta.description || meta.shortDescription || '';
          if (!name) continue;
          var values = {};
          var dwv = s.dataWindowView();
          if (dwv) {
            var items = dwv.items();
            if (items) {
              for (var i = 0; i < items.length; i++) {
                var item = items[i];
                if (item._value && item._value !== '∅' && item._title) {
                  values[item._title] = item._value;
                }
              }
            }
          }
          if (Object.keys(values).length > 0) results.push({ name: name, values: values });
        } catch(e) {}
      }
      return results;
    })()
    ```

### B. DOM Selectors (Alternative Fallbacks)
If the internal TradingView API is not loaded or has changed, DOM selectors can extract visual elements from the page:
- **Active Symbol Name**:
  - `document.querySelector('[data-name="legend-source-title"]')`
  - `document.querySelector('[class*="title"] [class*="apply-common-tooltip"]')`
  - `document.querySelector('.legend-item-title__text')`
- **Price**:
  - `document.querySelector('[class*="headerRow"] [class*="last-"]')`
  - `document.querySelector('[class*="bid"] [class*="price"], [class*="dom-"] [class*="bid"]')`
  - Parser for `document.title` (e.g., `"BTCUSDT 67450.50 ... - TradingView"`).
- **Timeframe Interval**:
  - `document.querySelector('[data-name="header-toolbar-intervals"] [class*="selected-"]')`
  - `document.querySelector('button[class*="isActive-"]')`
- **Indicator Values (from Pane Legend)**:
  - Select pane legend rows: `document.querySelectorAll('[class*="legendItem-"], .legend-item')`
  - Under each legend row:
    - Study Name: `row.querySelector('[class*="title-"], .legend-item__title')`
    - Study Values: `row.querySelectorAll('[class*="value-"], .legend-item__value')` (parsing title and textual values inside the legend).

---

## 3. Retrieval of Study Values (SMA50, SMA150, SMA200, ATR14)

In `nerves/workers/trading/mcp_client.py`, the `get_study_values(self, symbol, timeframe)` method handles study values retrieval:
1. It navigates to the target symbol: `await self._run("symbol", symbol)`
2. It changes to the target timeframe: `await self._run("timeframe", timeframe)`
3. It fetches active indicators and their data window values: `raw = await self._run("values")`
4. The `"values"` command in `tradingview-mcp` executes `core.getStudyValues()`, returning a list of `{ name: study_name, values: { title: value } }`.
5. It then searches the `indicators` dictionary using a fuzzy matching function `_find(keys)`:
   - **SMA50**: Looks for `"sma 50"`, `"sma50"`, `"ma 50"`, or `"ma50"` (case-insensitive substring matches).
   - **SMA150**: Looks for `"sma 150"`, `"sma150"`, `"ma 150"`, or `"ma150"`.
   - **SMA200**: Looks for `"sma 200"`, `"sma200"`, `"ma 200"`, or `"ma200"`.
   - **ATR14**: Looks for `"atr"` or `"average true range"`.
   - **Volume MA20**: Looks for `"vol ma"`, `"volume ma"`, `"vol avg"`, or `"vma"`.
   - **52w High/Low**: Looks for `"52w high"`, `"52 week high"`, `"yearly high"`, etc.

---

## 4. Fallback Strategy if DOM/API Extraction Fails

If both DOM selectors and the JS-based API parsing fail to retrieve the active symbol name (e.g. due to connection issues, slow loading, or breaking changes in the TradingView DOM layouts), the system implements the following fallback strategy:

1. **Active Ticker Resolution Fallback**:
   - When resolving the target chart context or generating screenshots, if the parsed ticker string is empty or invalid, the client falls back to using **`BTCUSDT`** or **`TAOUSDT`** as the default tickers.
   - For example, in local capture clients or integration harnesses, a request for `"active"` symbol that fails DOM lookup is directed to `"BTCUSDT"` or `"TAOUSDT"`.
2. **Graceful Error Recovery**:
   - If study indicators (SMA50, SMA150, SMA200, ATR14) cannot be found, `_find()` returns `None`.
   - Missing indicator values are bypassed in Pydantic validation (since Pydantic fields in `TradingViewAlertPayload` are defined as `Optional[Any]`), allowing the system to log a warning, register the signal as a base quote, and proceed without crashing the event loop or the FastAPI webhook receiver.
