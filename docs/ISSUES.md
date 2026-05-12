# QA Issues & Resolves - TradingView Edge Server

## Resolved Issues

### 1. Pytest Hang on Startup (Module Graph Initialization)
* **Symptom:** Running `pytest` or `pytest -v tests/` hangs indefinitely right after collecting test items, specifically blocking before the first test (`test_auth.py` or `test_webhook.py`).
* **Root Cause:** The `vision.py` module was doing top-level global imports of `vertexai` and `google.generativeai`. During the FastAPI `lifespan` initialization inside `ASGITransport(app=app)`, these libraries attempted to perform blocking HTTP I/O (like checking GCP credentials or metadata) which caused the asyncio event loop in `pytest_asyncio` to deadlock.
* **Resolution:** Refactored `vision.py` to use lazy (inner) imports. The `vertexai`, `anthropic`, and `google.generativeai` libraries are now only imported and initialized inside the `analyze_chart_vision` function body. 
* **Status:** FIXED.

### 2. End-to-End Test 401 Unauthorized Errors
* **Symptom:** `test_valid_1h_buy_webhook`, `test_invalid_4h_buy_webhook`, and `test_missing_interval_webhook` in `tests/e2e/test_end_to_end.py` failed with `401 Unauthorized` (assert 401 == 200).
* **Root Cause:** The `WEBHOOK_SECRET` in `tests/mock_data/payloads.json` did not match the environment's `WEBHOOK_SECRET` override defined in `tests/conftest.py` (`"test-secret"`).
* **Resolution:** Updated `test_end_to_end.py`'s `load_payloads()` function to dynamically inject `config.WEBHOOK_SECRET` into the valid payload dictionaries right after parsing JSON from disk.
* **Status:** FIXED.

### 3. Deprecated AsyncClient Instantiation
* **Symptom:** `TypeError: AsyncClient.__init__() got an unexpected keyword argument 'app'` in `tests/e2e/test_end_to_end.py`.
* **Root Cause:** The `httpx.AsyncClient` API changed and no longer accepts `app=app` directly for ASGI routing.
* **Resolution:** Replaced `AsyncClient(app=app, ...)` with `AsyncClient(transport=ASGITransport(app=app), ...)` in the end-to-end testing suite.
* **Status:** FIXED.

### 4. General Test Environment Isolation
* **Symptom:** Potential race conditions with external background tasks (MCP, Telegram Bot, APScheduler).
* **Root Cause:** If tests spin up real Telegram polling or APScheduler cron tasks, the tests leak threads and network connections.
* **Resolution:** Added explicit `config.*_ENABLED = False` statements at the very start of `conftest.py`'s `client` fixture to completely stub out all external Daemons during the test run.

## Active Issues / Known Limitations

### 1. Latency under Load (Pending Test)
* **Description:** The integration between RAG (Anthropic/Gemini) and Telegram formatting adds a 3-8 second latency. We need to implement a true asynchronous worker queue if high-frequency trading webhooks are expected. Currently, requests are handled via FastAPI's `BackgroundTasks`, which might clog up memory if thousands of requests hit simultaneously.
* **Action Item:** Monitor production logs. If necessary, refactor `background_tasks.add_task(execute_trade_and_notify, ...)` to utilize a Redis/Celery queue.

### 2. MCP Connectivity Error Handling
* **Description:** If the TradingView MCP server dies or the Chrome CDP connection drops, the bot still proceeds but logs `[Brief] Screenshot failed`.
* **Action Item:** Need more robust retry mechanisms and circuit breakers in `mcp_client.py` for headless Chrome crashes.
