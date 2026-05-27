## 2026-05-27T12:14:01Z
You are TV Study Extractor Explorer. Your task is to investigate how to extract the active symbol and study values (SMA50, SMA150, SMA200, ATR14) from the TradingView Desktop interface.
Specifically:
1. Examine the `tradingview-mcp` code (especially `tradingview-mcp/src/connection.js`, `tradingview-mcp/src/core/indicators.js`, and `tradingview-mcp/src/cli/commands/indicator.js`) to see how indicator values and active symbols are currently queried.
2. Determine what DOM selectors or JS expressions can retrieve the active symbol name, price, timeframe interval, and indicator values directly from the chart page.
3. Identify how the study values like SMA50, SMA150, SMA200, and ATR14 are retrieved (look at the `get_study_values` method in `nerves/workers/trading/mcp_client.py`).
4. Detail the fallback strategy if DOM extraction fails (using BTCUSDT or TAOUSDT).
Write your analysis and findings to `c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\explorer_m1_2\analysis.md`.
