# Handoff Report: R3. Multi-Channel Alerting on Failure

## 1. Observations
Direct code observations and evidence collected during the investigation:

* **Telegram Alerts Integration**: 
  In `nerves/workers/trading/notifier.py`, the notification system is structured as:
  ```python
  56: async def send_telegram_alert(message: str):
  ...
  62:     html_message = sanitize_for_telegram_html(message)
  ```
  And its synchronous runner wrapper:
  ```python
  101: def send_telegram_message(message: str):
  ```
  Which handles formatting of headings, bold, monospace, and lists under `sanitize_for_telegram_html` (lines 8-54).

* **Settings Storage**:
  In `nerves/workers/trading/database.py`, settings get/set functions read and write to the SQLite database `settings` table asynchronously:
  ```python
  316: async def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
  ...
  328: async def set_setting(key: str, value: str) -> None:
  ```

* **Aggregation Endpoint**:
  In `nerves/workers/trading/main.py`, aggregate statuses are returned via:
  ```python
  1318: @app.get("/api/system/status")
  1319: async def system_status_endpoint():
  ```

* **Frontend Dashboard Rendering**:
  In `nerves/workers/trading/static/dashboard.html` (lines 942-943), the system status panel is defined:
  ```html
  <div id="tab-status" class="tab-panel">
    <div id="statusGrid" class="status-grid">
  ```
  In `nerves/workers/trading/static/js/dashboard-core.js` (lines 332-362), the function `loadSystemStatus()` fetches from `/api/system/status` and injects status cards directly into `statusGrid.innerHTML`.

* **Logging Directory**:
  In `nerves/workers/trading/config.py` (line 16), general trades logging path is defined:
  ```python
  LOG_FILE = os.getenv("LOG_FILE", "trades.log")
  ```

---

## 2. Logic Chain
1. **Subprocess Pytest Execution**: Calling `pytest.main()` inside the parent application loop creates dependency caching conflicts and test pollution. Running `pytest` in a separate subprocess (e.g. `run_tests_helper.py` using `subprocess.run()`) ensures process isolation.
2. **Native Hook Capture vs. Regex**: Programmatic parsing of stdout via regex is error-prone. Implementing `pytest_runtest_logreport` hook inside a helper script enables native, structured capture of failed tests, location, and traceback.
3. **Traceback Shortening**: Pytest tracebacks can span hundreds of lines, exceeding Telegram's 4096-character API limit. Collecting the final `reprcrash` or slicing the last 8 lines of `longrepr` yields a concise, informative traceback.
4. **Synchronous DB Writes**: The watcher file runner is designed to execute as a CLI tool or thread, which may lack an active asyncio event loop. Using `sqlite3.connect()` synchronously to write `test_runner_status` to the settings table of `trades.db` prevents loop conflicts.
5. **Dashboard State Updates**: The UI periodically polls `/api/system/status`. Injecting the test runner and health check settings into the endpoint JSON and rendering them as cards in `statusGrid.innerHTML` will seamlessly reflect status changes.
6. **Telegram Hooking**: `notifier.send_telegram_message` is thread-safe and synchronous, making it perfect for direct invocation by both the CLI auto-test runner and APScheduler health check threads.

---

## 3. Caveats
- **Alert Rate Limiting**: If there are many failing tests, sending a separate Telegram alert for each failure may hit Telegram API rate limits. The implementation should group multiple failures into a single summarized report message if they exceed a threshold (e.g., >3 failures).
- **Environment Context**: This analysis assumes that the watcher (R1) and system health checks (R2) run in directories sharing `config.py` definitions (specifically `config.DB_PATH` and `config.TELEGRAM_BOT_TOKEN`).

---

## 4. Conclusion
R3 can be implemented cleanly by:
1. Creating a `run_tests_helper.py` script that runs pytest programmatically and outputs failure JSON to stdout.
2. Creating an `alert_manager.py` module to log failures to `nerves/workers/trading/test_runs.log`, save status to `trades.db` settings, and send markdown-sanitized Telegram notifications.
3. Hooking the test runner and health checks to `alert_manager.py`'s handle functions.
4. Updating `/api/system/status` and `dashboard-core.js` to serve and render status updates.

---

## 5. Verification Method
1. **Log File**: Verify `test_runs.log` exists in `nerves/workers/trading/` and format follows:
   `[Timestamp] | ERROR | Test Run FAILED: 1/X tests failed.`
2. **Integration Test**: Intentionally write a failing test under `tests/unit/` (e.g. `assert False`), trigger the watcher, and verify:
   - File `test_runs.log` captures the failure.
   - Database `settings` table updates: `test_runner_status = "failed"`.
   - Telegram message is received with the test name and the 8-line traceback.
3. **Liveness Test**: Run pytest command in `nerves/workers/trading/` to ensure no syntax errors exist in the test files:
   `python -m pytest`
