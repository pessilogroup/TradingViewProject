# Handoff Report — Webhook Ingress and Persistence Layers Analysis

## 1. Observation
We observed the following exact file locations, code blocks, and execution results during the read-only investigation:

- **Webhook Ingress Implementation**: 
  - File: `nerves/workers/trading/gateway/webhook.py` (lines 45–230)
  - Endpoint path: `/webhook` via `@router.post("/webhook")`
  - Integration: Registered in `nerves/workers/trading/main.py` (lines 41, 273):
    ```python
    from gateway.webhook import router as _webhook_router
    ...
    app.include_router(_webhook_router)
    ```

- **Pydantic Data Model**:
  - File: `nerves/workers/trading/data/tv_models.py` (lines 9–42)
  - Model class: `class TradingViewAlertPayload(BaseModel)`
  - Model config: `model_config = ConfigDict(populate_by_name=True, extra="allow")` (line 42)
  - Key fields (with aliases/defaults):
    - `secret`: `Optional[str]`
    - `action`: `Optional[str]` (alias `side`)
    - `symbol`: `Optional[str]`
    - `price`: `Optional[Any]`
    - `volume`: `Optional[Any]`
    - `quoteQty`: `Optional[Any]` (alias `size`, default `10.0`)
    - `time`: `Optional[str]`
    - `interval`: `Optional[str]`
    - `sl`: `Optional[str]`
    - `tp`: `Optional[str]`
    - `exchange`: `Optional[str]`
    - `indicator`: `Optional[str]`
    - `strategy`: `Optional[str]`
    - `message`: `Optional[str]`

- **Security Validation Logic**:
  - Timing-attack safe comparison (lines 76–80 in `webhook.py`):
    ```python
    if not is_dashboard_user and not secrets.compare_digest(
        str(secret), str(config.WEBHOOK_SECRET)
    ):
    ```
  - IP Whitelisting (lines 286–308 in `main.py`): Real client IP extracted from rightmost hop of `X-Forwarded-For` header. Checks against `config.TV_WHITELIST_IPS`.
  - Rate Limiting (lines 113–122 in `webhook.py`): 15 requests per minute limit tracked in `_WEBHOOK_RATE_LIMITS` keyed by IP.

- **Persistence Layer**:
  - Database Path: `config.DB_PATH` defaulting to `trades.db` in project root directory (lines 19 in `config.py`).
  - SQLite Schema for `indicator_signals` (lines 108–122 in `database.py`):
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
    ```
  - Insertion logic: Main signal insertion occurs in `persistence_store.py` (lines 14–32), followed by a background event `IndicatorSignalReceived` if `is_indicator` is true (lines 201–213 in `webhook.py`). The listener in `nerves/workers/trading/data/indicator_persistence.py` executes `insert_indicator_signal` in `persistence_store.py` (lines 43–72) inside a `try/except` block (Design Invariant DI-1) so database errors do not block the trading pipeline.

- **Test Suite Results**:
  - Ran unit tests in `nerves/workers/trading/tests/unit/test_webhook_gateway.py` (15/15 PASSED in 1.35s).
  - Ran integration tests in `nerves/workers/trading/tests/integration/test_webhook.py` (2/2 PASSED in 2.90s).

---

## 2. Logic Chain
1. **Endpoint Routing**: The main FastAPI instance `app` in `main.py` imports and mounts the `_webhook_router` from `gateway.webhook`. Therefore, any POST request to `/webhook` routes directly to the `webhook(request: Request)` handler in `webhook.py`.
2. **Payload Parsing & Model Injection**: The incoming request body is parsed as JSON, and parsed into the Pydantic class `TradingViewAlertPayload` using `model_validate`. This handles snake_case to camelCase conversion (e.g. `size` -> `quoteQty`).
3. **Multi-layer Security**: 
   - Requests are verified against whitelisted TradingView IPs using global middleware if enabled (`config.ENABLE_IP_WHITELIST`). Client IP is resolved using the rightmost hop of `X-Forwarded-For` to prevent IP header spoofing.
   - The token secret is compared using timing-attack safe `secrets.compare_digest` with `config.WEBHOOK_SECRET`. A Bearer token matching `config.DASHBOARD_TOKEN` acts as a bypass.
   - Client IPs are rate-limited to 15 req/min via an in-memory sliding window cache.
4. **Data Isolation and DB Persistence**:
   - The secret is stripped (`payload.pop("secret", None)`) prior to storing in the database to prevent credential leakage.
   - `is_indicator` is evaluated to check if the payload originates from an indicator. If so, a sanity check requires both `symbol` and `indicator_name` to be present (raising a HTTP 400 bad request if missing).
   - If validation passes, a parent signal record is saved to the `signals` table via `database.insert_signal`.
   - For indicator signals, `IndicatorSignalReceived` event is emitted. The subscriber in `indicator_persistence.py` handles asynchronously inserting the corresponding indicator metadata and parameters into the `indicator_signals` table via a robust, non-blocking try-except wrapper.

---

## 3. Caveats
- **IP Whitelist Status**: IP Whitelisting is controlled by the environment variable `ENABLE_IP_WHITELIST` (defaulting to `false` in development). If disabled, requests from any IP can reach the webhook authentication.
- **In-Memory Rate Limiting**: The rate-limit cache `_WEBHOOK_RATE_LIMITS` is in-memory. In a distributed/multi-process server environment, this cache is isolated to each process.
- **Async DB Lock**: While database operations are asynchronous using `aiosqlite`, SQLite has a database-level lock during write transactions. High concurrency of webhook signals could cause transactional queuing.

---

## 4. Conclusion
The webhook ingress and persistence layers are robustly implemented with strong security guards (timing-safe token validation, IP-spoofing-resistant whitelisting, and in-memory rate limiting). The expected payload schema is highly flexible, utilizing Pydantic's alias matching and `extra="allow"` configuration. Database persistence enforces proper normalization across `signals` and `indicator_signals` tables, executing database writes asynchronously and isolating potential DB errors from blocking the core execution pipeline (DI-1).

---

## 5. Verification Method
To verify the webhook validation, parsing, and persistence layers independently:
1. Run the test suite:
   ```powershell
   pytest nerves/workers/trading/tests/unit/test_webhook_gateway.py
   pytest nerves/workers/trading/tests/integration/test_webhook.py
   ```
2. Manually test webhook routing and validation using PowerShell:
   ```powershell
   # Send an unauthorized payload (returns 401)
   Invoke-RestMethod -Method Post -Uri "http://localhost:5000/webhook" -ContentType "application/json" -Body '{"symbol": "BTCUSDT", "side": "BUY"}'
   ```
3. Inspect database schema structure directly using SQLite CLI on the target db:
   ```powershell
   sqlite3 trades.db ".schema indicator_signals"
   ```
