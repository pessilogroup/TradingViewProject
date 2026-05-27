# Webhook Ingress and Persistence Layers Analysis

This report documents the detailed investigation of the TradingView webhook ingress, security validation, Pydantic schema models, and SQLite persistence layers within the TradingViewProject codebase.

---

## 1. Webhook Ingress Implementation

The `/webhook` endpoint is implemented inside the **FastAPI** web application. 

* **File Location**: `nerves/workers/trading/gateway/webhook.py` (lines 45–230)
* **Function**: `async def webhook(request: Request)`
* **Route Mapping**: Registered via the APIRouter instance `router = APIRouter()` and decorated with `@router.post("/webhook")`.
* **Server Setup & Mount**: In `nerves/workers/trading/main.py` (lines 41 and 273), the router is imported and mounted onto the core `FastAPI` instance:
  ```python
  from gateway.webhook import router as _webhook_router
  ...
  app.include_router(_webhook_router)
  ```

---

## 2. Expected Pydantic Schema & Payload Requirements

The Pydantic data model validates and parses incoming payloads into structured python objects.

* **File Location**: `nerves/workers/trading/data/tv_models.py`
* **Model Class**: `TradingViewAlertPayload(BaseModel)`
* **Model Configuration**: `model_config = ConfigDict(populate_by_name=True, extra="allow")`. This configuration maps incoming payload keys (which may use snake_case or camelCase aliases) and allows additional custom keys to be parsed without raising validation exceptions.

### Table of Expected Payload Fields:

| Field Name | Type | Alias | Default | Description / Expected Values |
| :--- | :--- | :--- | :--- | :--- |
| `secret` | `Optional[str]` | — | `None` | Authentication secret key. |
| `action` | `Optional[str]` | `side` | `None` | The trade action, typically `"buy"`, `"sell"`, or `"alert"`. |
| `symbol` | `Optional[str]` | — | `None` | Trading pair symbol, e.g., `"BTCUSDT"`, `"ETHUSDT"`. |
| `price` | `Optional[Any]` | — | `None` | Market price at the time of the alert (coerced safely downstream). |
| `volume` | `Optional[Any]` | — | `None` | Transaction volume at the time of the alert. |
| `quoteQty` | `Optional[Any]` | `size` | `10.0` | Quote quantity for trade execution (capped at `MAX_QUOTE_QTY`). |
| `time` | `Optional[str]` | — | `None` | Timestamp of the signal event from TradingView. |
| `interval` | `Optional[str]` | — | `None` | Timeframe/interval of the chart (e.g., `"1m"`, `"5m"`, `"1h"`, `"D"`). |
| `sl` | `Optional[str]` | — | `None` | Stop Loss trigger price or percentage. |
| `tp` | `Optional[str]` | — | `None` | Take Profit trigger price or percentage. |
| `exchange` | `Optional[str]` | — | `None` | Target exchange (e.g., `"binance"`, `"bybit"`, `"weex"`). |
| `indicator` | `Optional[str]` | — | `None` | Name of the indicator triggering the alert (e.g., `"MTT"`). |
| `strategy` | `Optional[str]` | — | `None` | Name of the strategy. |
| `message` | `Optional[str]` | — | `None` | Custom text alert details from TradingView. |

---

## 3. Webhook Signal Validation Logic

Incoming webhook requests undergo a multi-layered security validation process to check credentials, IP rate limits, and whitelisting.

### A. Authentication and Secrets
Validation is processed in `nerves/workers/trading/gateway/webhook.py` (lines 59–80):
1. **Secret Lookup**: The webhook endpoint tries to retrieve the authentication secret from three distinct sources in order:
   - Header: `X-TV-Secret`
   - Query Parameter: `?secret=...`
   - JSON Payload: `payload["secret"]`
2. **Dashboard Bypass**: If the request contains a valid `Authorization` header with a Bearer token matching `config.DASHBOARD_TOKEN`, the webhook secret check is bypassed.
3. **Comparison**: If not bypassed, it performs a timing-attack safe comparison using `secrets.compare_digest(str(secret), str(config.WEBHOOK_SECRET))`. Failing checks reject with `HTTP 401 Unauthorized`.
4. **Secret Stripping**: Once validated, the `secret` key is popped from the payload dict (`payload.pop("secret", None)`) so it is never logged or stored in the database.

### B. IP Whitelisting
IP whitelisting is handled globally by the HTTP middleware `ip_whitelist_middleware` in `nerves/workers/trading/main.py` (lines 298–308):
* **State Check**: Enabled if `config.ENABLE_IP_WHITELIST` is `True`.
* **Client IP Extraction (Anti-Spoofing Fix SEC-001)**: The client IP is extracted via a helper function `_get_real_client_ip(request)` (lines 289–295) that parses the `X-Forwarded-For` header and extracts the **rightmost** IP entry. This rightmost entry is appended by the trusted reverse proxy, preventing clients from spoofing their IP address via custom headers.
* **IP Restriction**: If the extracted IP is not `"127.0.0.1"` and is not in the set of whitelisted TradingView IPs (`config.TV_WHITELIST_IPS`), the request is rejected with `HTTP 403 Forbidden`. The default whitelisted IPs are:
  - `"52.89.214.238"`
  - `"34.212.75.30"`
  - `"54.218.53.128"`
  - `"52.32.178.7"`

### C. Rate Limiting
Rate limiting is evaluated directly within the `/webhook` endpoint in `nerves/workers/trading/gateway/webhook.py` (lines 113–122):
* **Limit**: Standard rate limit of **15 requests per minute** per client IP.
* **Mechanism**: State is held in a module-level dictionary `_WEBHOOK_RATE_LIMITS = {}` storing `(count, window_start_timestamp)` keyed by the source IP.
* **Limiting**: If the current request time is within 60 seconds of `window_start_timestamp` and the count is $\ge 15$, it rejects with `HTTP 429 Too Many Requests`. Otherwise, it updates the count or resets the window.

### D. Safe Parsing and Input Sanitization
To avoid parsing issues and potential denial-of-service/overflow vulnerabilities (TVP-001 / CWE-20 & TVP-002 / CWE-770), the webhook performs safe type coercion:
* **Price Parsing**: Removes commas from string values and converts to float: `float(str(price).replace(',', ''))`. If parsing fails, it defaults to `None`.
* **Quantity Parsing**: Converts `quoteQty` to a float. If missing or invalid, it defaults to `10.0`. If it exceeds `config.MAX_QUOTE_QTY`, it is capped at that limit.

---

## 4. Database Persistence Structure

### A. Database Location
The SQLite database path is resolved using the `DB_PATH` environment variable, managed through `config.py` (lines 19 and 23):
* **Default Location**: `trades.db` in the workspace root path (or `/app/data/trades.db` in the production Docker container).
* **Current Workspace File**: `c:\Users\pesil\working\mj_trading\TradingViewProject\trades.db`

### B. SQLite Schema of the `indicator_signals` Table
The schema is defined in `nerves/workers/trading/database.py` (lines 108–127):

```sql
CREATE TABLE IF NOT EXISTS indicator_signals (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id        INTEGER NOT NULL REFERENCES signals(id),
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    symbol           TEXT    NOT NULL,
    indicator_name   TEXT    NOT NULL,
    signal_type      TEXT    NOT NULL DEFAULT 'info',
    interval         TEXT,
    price            REAL,
    confidence_score INTEGER DEFAULT 0,
    conditions_met   TEXT,
    metadata         TEXT,
    source_ip        TEXT,
    exchange         TEXT    DEFAULT 'binance'
);

-- Index Definitions
CREATE INDEX IF NOT EXISTS idx_indicator_signals_symbol ON indicator_signals(symbol);
CREATE INDEX IF NOT EXISTS idx_indicator_signals_name   ON indicator_signals(indicator_name);
CREATE INDEX IF NOT EXISTS idx_indicator_signals_type   ON indicator_signals(signal_type);
CREATE INDEX IF NOT EXISTS idx_indicator_signals_date   ON indicator_signals(created_at);
```

### C. Step-by-Step Data Persistence Flow
1. **General Signal Storage**:
   The `/webhook` endpoint first inserts the incoming request payload details into the main `signals` table via `database.insert_signal(...)` (written in `nerves/workers/trading/data/persistence_store.py`). This returns a new `signal_id`.
2. **Indicator Signal Identification**:
   The endpoint checks if the signal is from an indicator. It parses custom keys like `source` and `indicator_name` (lines 136–140):
   ```python
   source = payload.get("source", "")
   indicator_name = payload.get("indicator_name", "") or payload.get("indicator", "") or ""
   is_indicator = source == "indicator" or (indicator_name and action not in {"buy", "sell", "alert"})
   ```
3. **Payload Guard**:
   If identified as an indicator signal, the webhook performs a sanity check: both `symbol` and `indicator_name` must be present. If missing, it immediately rejects with `HTTP 400` without inserting database entries.
4. **Asynchronous Event Dispatch**:
   If the indicator checks pass, the webhook issues a background event dispatch via the `EventBus`:
   ```python
   await _event_bus.emit_background(IndicatorSignalReceived(
       signal_id=signal_id,
       symbol=symbol,
       indicator_name=indicator_name,
       signal_type=signal_type,
       ...
   ))
   ```
5. **Parallel Listener Persistence (Design Invariant DI-1)**:
   The `IndicatorPersistence` listener (defined in `nerves/workers/trading/data/indicator_persistence.py`) subscribes to the `IndicatorSignalReceived` event.
   - It intercepts the event and executes `insert_indicator_signal(...)` using the `aiosqlite` asynchronous driver.
   - Values are serialized (e.g., `conditions_met` and `metadata` are stored as JSON strings).
   - **Fault Isolation**: A try/except block wraps the entire database insert inside the listener. If database operations fail, errors are logged but not re-raised. This ensures that persistence failures do not block the active trade pipeline.
