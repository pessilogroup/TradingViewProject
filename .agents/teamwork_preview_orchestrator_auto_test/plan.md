# plan.md — teamwork_preview_orchestrator_auto_test

## Architecture & Integration Specs

### 1. Watcher-Based Auto-Test Execution (R1)
- **Path to Watch**: `nerves/workers/trading/` and `pine/` directories.
- **Files**: Detect modifications to `.py` and `.pine` files.
- **Debounce**: >= 1.0 second debounce delay. Multiple files written within the debounce window must be aggregated and trigger a single test suite execution.
- **Implementation**:
  - Write an async script at `nerves/workers/trading/scripts/autotest_watcher.py`.
  - Use `watchfiles.awatch` as the primary watcher.
  - Implement a standard-library fallback `PollingWatcher` using `os.walk` and `os.stat` with a polling interval of 0.5s if `watchfiles` fails to start or import.
  - Manage debounce using an `asyncio.Queue`. When a file change event is received, push it to the queue. Have a consumer task that:
    1. Waits for the first event in the queue.
    2. Enters a sleep loop of 1.0s, draining any subsequent events from the queue (resetting/updating the last-seen time).
    3. Triggers the test suite once 1.0s has elapsed without any new event.
  - Run the test suite by spawning a separate process: `sys.executable -m pytest` under the `nerves/workers/trading/` directory. Do NOT use `pytest.main()` inside the watcher process to avoid caching issues.
  - Capture pytest stdout and stderr to parse the test results.

### 2. System Health & Integration Verification (R2)
- **Check Intervals**: Every 30 seconds, run in a background task within the `autotest_watcher.py` daemon.
- **Verification Operations**:
  - **Database connection check**: Attempt an async write and read using `database.set_setting("health_check_ping", timestamp)` and `database.get_setting("health_check_ping")`. If it succeeds, database health is "OK". If it raises an exception, it is "ERROR".
  - **API Server liveness check**: Attempt an async TCP handshake to `127.0.0.1:5000` using `asyncio.open_connection("127.0.0.1", 5000)`. If successful, health is "OK", else "ERROR".
  - **TradingView CDP liveness check**: Attempt an async TCP handshake to `127.0.0.1:9222` using `asyncio.open_connection("127.0.0.1", 9222)`. If successful, health is "OK", else "ERROR".
- **Dashboard Visibility**:
  - Persist health status to the settings table using database settings helpers:
    - Key: `health_api_server` -> "OK" or "ERROR"
    - Key: `health_cdp` -> "OK" or "ERROR"
    - Key: `health_database` -> "OK" or "ERROR"
    - Key: `test_runner_status` -> "PASSING" or "FAILING"
    - Key: `last_test_run` -> JSON string with `timestamp`, `status`, `summary`, and `error_log` (shortened traceback)

### 3. Multi-Channel Alerting on Failure (R3)
- **Log File**: Log test runs, results, and health failures to `nerves/workers/trading/test_runs.log`.
- **Telegram Bot Alerting**:
  - When a test run fails, or when a health check transitions from "OK" to "ERROR", send an urgent Telegram alert using the existing `notifier.send_telegram_message` (which handles html-sanitization and environment settings).
  - Rate-limit/group alerts to avoid hitting Telegram API rate limits if many tests fail simultaneously.
  - The Telegram message must contain:
    - The offending file name (or health check name).
    - A shortened traceback: capture the final `reprcrash` from pytest or slice the last 8 lines of the failure traceback.
- **Centralized Alert Manager**:
  - Implement alert manager logic in `nerves/workers/trading/alert_manager.py` (or directly within the watcher/status check framework).
  - Handle updating DB settings, logging to `test_runs.log`, and dispatching Telegram messages.

### 4. API and Dashboard UI Extensions
- **FastAPI Endpoint Update**:
  - Update `nerves/workers/trading/main.py` `/api/system/status` endpoint to query the settings table for health status keys (`health_api_server`, `health_cdp`, `health_database`, `test_runner_status`, `last_test_run`) using `database.get_setting`.
  - Include these keys in the returned JSON structure.
- **Frontend Dashboard Update**:
  - Update `nerves/workers/trading/static/js/dashboard-core.js` in `loadSystemStatus()`.
  - Append custom HTML cards to `statusGrid` displaying the current state of:
    - Auto-Test Runner status (PASSING/FAILING, and last run time).
    - API Server health.
    - TV CDP health.
    - Database health.

---

## Execution Verification Plan

### Step 1: Implementation
Spawn a single Worker to implement the watcher script, database health integration, alert manager, FastAPI endpoint updates, and javascript dashboard updates.

### Step 2: Code Review
Spawn two Reviewers to independently examine the implementation for:
- Proper debounce locking/queuing.
- Correct asynchronous error handling for DB/port check connections.
- Code style and safety constraints.

### Step 3: Empirical Testing (Challenger)
Spawn Challengers to simulate failures:
- Shut down API server / CDP port and verify they register as ERROR.
- Inject a failing test in pytest and verify that:
  - `test_runs.log` contains the failure.
  - `test_runner_status` updates to "FAILING" in the DB.
  - A Telegram message with the filename and 8-line traceback is sent.

### Step 4: Forensic Audit
Invoke the Forensic Auditor to verify that the implementation is genuine, clean, and has no integrity issues.
