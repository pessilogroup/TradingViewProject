Create the Python integration script that automates connecting to TradingView Desktop via CDP, extracts active symbol, price, interval, and studies, and sends a validated webhook payload.

Please perform the following tasks:

1. Fix the study values extraction bug in `nerves/workers/trading/mcp_client.py`'s `get_study_values` method (around line 144-176). The CLI output returns studies in the format `{ "studies": [ { "name": "Study Name", "values": { "key": "value" } } ] }`. Modify `get_study_values` so that if the returned dict does not contain `"indicators"`, but contains `"studies"`, it flattens the list of studies into a flat dictionary `indicators` where the keys are formatted as `"{name} {key}"` and `"{name}"` to match what `_find` looks for.

2. Implement a new script `nerves/workers/trading/scripts/tv_cdp_webhook.py`. The script must:
   - Check if CDP is already listening on port 9222 by making a GET request to `http://localhost:9222/json/version`.
   - If not, auto-launch TradingView Desktop on Windows:
     - First, check the standard installation paths (like `%LOCALAPPDATA%\TradingView\TradingView.exe`, `%PROGRAMFILES%\TradingView\TradingView.exe`, and `%PROGRAMFILES(X86)%\TradingView\TradingView.exe`).
     - If not found in standard paths, run a PowerShell command to dynamically query the installation location of the MSIX package:
       `Get-AppxPackage -Name "TradingView.Desktop"`
       Extract its `InstallLocation` and locate `TradingView.exe` inside it.
     - Launch the resolved executable with the argument `--remote-debugging-port=9222` without requiring Administrator privileges (execute the binary directly using `subprocess.Popen` or PowerShell `Start-Process`).
     - Poll `http://localhost:9222/json/version` (up to 20 seconds, checking every 1 second) to verify CDP is up.
   - Extract active symbol, timeframe resolution, and current price from the active chart:
     - Query active symbol by executing: `node tradingview-mcp/src/cli/index.js symbol` (or use MCPClient / getState).
     - Query current timeframe by executing: `node tradingview-mcp/src/cli/index.js timeframe` (or extract from the state/symbol output).
     - Query close price by executing: `node tradingview-mcp/src/cli/index.js quote` (or use the active price from the quote output).
     - Fallback: If symbol/studies extraction fails, log a warning and fall back to symbol `"BTCUSDT"` (or `"TAOUSDT"`), interval `"1h"`, price `68000.0`, and mock study values.
   - Extract study values (SMA50, SMA150, SMA200, ATR14) by running the values command:
     - Run `node tradingview-mcp/src/cli/index.js values` or utilize the updated `MCPClient` from `mcp_client.py` to extract them.
   - Build the webhook payload matching `TradingViewAlertPayload`:
     - `secret`: webhook secret token loaded from `nerves/workers/trading/.env` or `config.py` (e.g. `config.WEBHOOK_SECRET`).
     - `source`: `"indicator"`
     - `symbol`: extracted/fallback symbol
     - `indicator_name`: `"MultipleIndicators"`
     - `price`: extracted close price (float)
     - `interval`: extracted interval (e.g., `"60"`, `"D"`, `"1h"`, etc.)
     - `confidence_score`: 90
     - `conditions_met`: `["SMA50 > SMA150", "SMA150 > SMA200"]`
     - `metadata`: `{"sma50": sma50, "sma150": sma150, "sma200": sma200, "atr14": atr14}`
   - POST the payload to `http://localhost:5000/webhook` (or PORT from environment/config) and assert that it returns HTTP 200/202 with `{"received": true}`.

3. Verify the implementation:
   - Start the FastAPI server locally by executing `python nerves/workers/trading/start_server.py`.
   - Run the implementation script `tv_cdp_webhook.py`.
   - Direct-check persistence in the SQLite database `nerves/workers/trading/trades.db`: query the `indicator_signals` table to verify that the webhook signal was inserted and stored successfully.
   - Record the build/test results, commands executed, and layout verification details in your handoff report.
