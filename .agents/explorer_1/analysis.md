# Investigation Analysis Report

This report outlines the technical findings regarding the TradingView automation codebase, highlighting exact code paths, functional details, and architectural suggestions for Requirements R1 through R6.

---

## 1. Webhook Price Validation (R1)
### Current Implementation
- **Ingress point**: `nerves/workers/trading/gateway/webhook.py` inside the `@router.post("/webhook")` handler.
- **Parsing logic**:
  ```python
  try:
      price_float = float(str(price).replace(',', '')) if price else None
  except (ValueError, TypeError):
      price_float = None
  ```
- **Limitation**: Currently, there is no validation on whether `price_float` is positive or valid before writing to the database via `insert_signal()` or dispatching the event downstream. Only downstream components (e.g., `TradeEngine` and `SignalEnricher`) perform validation or emit warnings/failures when price is `None` or non-positive.
- **Goal constraint**: Invalid indicator payloads should not create orphan signal rows.

### Proposed Code Edit
Modify `nerves/workers/trading/gateway/webhook.py` before writing to the database:
```python
# Price and quantity validation
if price_float is not None and price_float <= 0.0:
    raise HTTPException(status_code=400, detail="Invalid price: must be greater than zero")

if not is_indicator and (price_float is None or price_float <= 0.0):
    raise HTTPException(status_code=400, detail="Price is required and must be positive for execution actions")
```

---

## 2. Order Types: MARKET vs LIMIT vs OCO (R2)
### Current Implementation
- **Orchestrator**: `nerves/workers/trading/engine/trade_engine.py` listens to `TradeApproved` and resolves the exchange adapter via `ExchangeRouter`. It calls `adapter.execute_smart_order(...)`.
- **Binance Adapter**: `nerves/workers/trading/exchanges/binance_adapter.py` maps to `binance_client.py`.
  - Supports `["MARKET", "LIMIT", "OCO"]`.
  - Places a **MARKET** order for entry (either quote_qty or base_qty).
  - Places an **OCO** order (consisting of a **LIMIT** maker for Take Profit and a **STOP_LOSS_LIMIT** for Stop Loss) on the opposite side to manage risk.
- **Weex Adapter**: `nerves/workers/trading/exchanges/weex_adapter.py`.
  - Supports `["MARKET", "LIMIT"]`. Since Weex lacks native OCO order execution, it places a **MARKET** order for entry (`open_long` / `close_long`) and simulates OCO by placing a **LIMIT** order for Take Profit (`close_short` / `close_long`) and returning it as a `"SIMULATED_OCO"`.

### Proposed Code Edit (Simplifying/Extending Adaptability)
If the implementer needs to unify limit order handling or custom risk, they can extend Weex's simulated OCO to poll or listen to triggers:
```python
# In weex_adapter.py - execute_smart_order
# Proposed structure to allow limit entries or better simulation:
# If limit order entry is requested, use orderType="limit" instead of "market"
```

---

## 3. Checking Available Binance/Weex Balances (R3)
### Current Implementation
- **Binance balance check**:
  - Path: `nerves/workers/trading/binance_client.py` -> `get_account_balance(self, asset="USDT")`
  - Logic: In dry run, it returns a mock `$10,000.00`. In live mode, it executes a signed `GET` to `/api/v3/account` and scans `balances` for `asset.upper()`.
- **Weex balance check**:
  - Path: `nerves/workers/trading/exchanges/weex_adapter.py` -> `get_account_balance(self, asset="USDT")`
  - Logic: In dry run, it returns `10000.0`. In live mode, it makes a signed `GET` to `/api/v2/contract/account/accounts` with query params `{"marginCoin": asset}` and retrieves the `available` property.

### Proposed Code Edit (Enhancing error-handling)
Ensure we fail gracefully if balance cannot be fetched:
```python
# In weex_adapter.py:
try:
    data = await self._request("GET", "/api/v2/contract/account/accounts", {"marginCoin": asset})
    # Parse available balance...
except Exception as e:
    log.error(f"Failed to fetch balance: {e}")
    return 0.0
```

---

## 4. Retrieving Latest Study Indicators & ATR Value (R4)
### Current Implementation
- **CDP Extraction**: `nerves/workers/trading/mcp_client.py` -> `MCPClient.get_study_values(self, symbol, timeframe)`
  - Runs the Node CLI wrapper (`node index.js values`) which calls Chrome DevTools Protocol commands on TradingView Desktop (CDP port 9222).
  - Searches the returned active studies on the chart for matching names (e.g. `atr` or `average true range`).
- **Algorithmic Fallback**: `nerves/workers/trading/analysis.py` -> `calculate_atr14` or `fetch_candles_with_retry`
  - Fetches 14 candles using aiohttp and computes the average true range:
    ```python
    atr14 = sum(tr_values[-14:]) / 14 if len(tr_values) >= 14 else None
    ```

### Proposed Code Edit (Robust matching)
Improve parsing indicators in `mcp_client.py`:
```python
# In mcp_client.py:
# Enhance the _find helper to handle exact and prefix match queries for indicators like ATR14, SMA50/150/200.
```

---

## 5. CDP Chrome Connection & Health Monitor Check (R5)
- **CDP Status Check**: `mcp_client.py`'s `health_check()` executes a subprocess status command to query if the DevTools protocol connection to TradingView Desktop is active.
- **Recurring Health Check**:
  - Place a new job in the Async scheduler `nerves/workers/trading/scheduler.py`:
    ```python
    async def check_cdp_connection_job():
        from mcp_client import get_mcp_client
        mcp = get_mcp_client()
        status = await mcp.health_check()
        if not status.get("connected"):
            logger.warning("CDP disconnected! Attempting reload/reconnect...")
            # Trigger reload or restart daemon commands here
    ```
  - Register it in `scheduler.py`'s `create_scheduler()` to run every 5 minutes.

---

## 6. Gemini Vision/Heuristic Regime Filter Flow (R6)
- **Path**: `nerves/workers/trading/analyzer/ai_analyzer.py` listens to `SignalValidated` -> triggers screenshot -> passes to `nerves/workers/trading/vision.py`.
- **Heuristic Regime Filter**:
  - In `vision.py` -> `analyze_chart_vision`, it invokes the Gemini model.
  - If visual pattern analysis returns Stage 3/4 Downtrend (heuristic check), it flags a Visual Veto:
    ```python
    if is_downtrend:
        result["verdict"] = "🔴 AVOID — Stage 3/4 Downtrend Detected"
    ```
  - This verdict is propagated via the `AnalysisComplete` event to the `NotificationHub` which decides whether to approve or reject the trade.
