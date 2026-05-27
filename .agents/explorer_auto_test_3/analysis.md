# Implementation Strategy: R3. Multi-Channel Alerting on Failure

This report provides a read-only investigation and design architecture to implement requirement **R3 (Multi-Channel Alerting on Failure)**. It addresses capturing test outputs, integrating with the Telegram notification module, log placement, and hooking the alerting system to both the auto-test watcher (R1) and the health check scheduler (R2).

---

## 1. Capturing Pytest Outputs & Formatting Shortened Tracebacks

Running tests programmatically within the main thread of a long-running web application can cause memory leaks, dependency caching issues, and test isolation failure. Therefore, tests must execute in a separate **subprocess**.

### Approach A: Subprocess with `pytest` CLI Output Parsing
We execute pytest using `subprocess.run` with `--tb=short` (which reduces traceback depth to only the assertion frame) and `--color=no` (to avoid parsing ANSI color codes).
```python
import subprocess

result = subprocess.run(
    ["pytest", "--tb=short", "--color=no", "nerves/workers/trading/tests/"],
    capture_output=True,
    text=True,
    encoding="utf-8"
)
```
We can parse `result.stdout` to capture the name of the failing test, the filename, and the exception. In pytest `--tb=short` output, failures start with a separator line `_________ test_name _________` and show the line of code that failed followed by lines prefixed with `E   ` explaining the error.

### Approach B: Programmatic Subprocess Helper with Custom Pytest Plugin (Recommended)
Rather than writing fragile regex parsers for console output, we write a programmatic helper script `run_tests_helper.py` that executes `pytest.main()` inside its subprocess. We inject a custom inline pytest plugin that intercepts test failure hooks natively.

#### File: `nerves/workers/trading/run_tests_helper.py` (Proposed)
```python
import pytest
import json
import sys

class FailureCapturer:
    def __init__(self):
        self.failures = []
        self.total = 0

    def pytest_runtest_logreport(self, report):
        # Count only when tests are executed (excluding setup/teardown unless setup fails)
        if report.when == "call":
            self.total += 1
            
        if report.failed:
            file_path, line_no, test_name = report.location
            
            # Extract the traceback traceback description
            longrepr_str = str(report.longrepr) if report.longrepr else ""
            tb_lines = longrepr_str.split("\n")
            
            # Format a shortened traceback: capture the last 8 lines
            short_tb = "\n".join(tb_lines[-8:]) if len(tb_lines) > 8 else longrepr_str
            
            error_msg = "Unknown Error"
            if hasattr(report.longrepr, "reprcrash"):
                error_msg = report.longrepr.reprcrash.message
            elif tb_lines:
                error_msg = tb_lines[-1]
                
            self.failures.append({
                "test_name": test_name,
                "file_path": file_path,
                "line_no": line_no,
                "error_message": error_msg,
                "short_traceback": short_tb
            })

if __name__ == "__main__":
    capturer = FailureCapturer()
    # Execute tests via pytest programmatically within this process
    pytest.main(["-q", "nerves/workers/trading/tests/"], plugins=[capturer])
    
    # Print the structured output to stdout
    print(json.dumps({
        "success": len(capturer.failures) == 0,
        "total_tests": capturer.total,
        "failures": capturer.failures
    }))
```
The watcher runner (R1) calls `python run_tests_helper.py` in a subprocess, reads the JSON from stdout, and gets a clean structured dictionary containing every failed test, its exact location, and a shortened traceback with 0 parsing errors.

---

## 2. Integrating with `notifier.py` for Telegram Alerts

The worker codebase has an existing notification module in `nerves/workers/trading/notifier.py`. It has:
1. `send_telegram_alert(message: str)`: An asynchronous function using `aiohttp` to broadcast alerts to all chat IDs in `config.TELEGRAM_CHAT_IDS`.
2. `send_telegram_message(message: str)`: A synchronous wrapper that schedules `send_telegram_alert` on the running asyncio loop (via `asyncio.run_coroutine_threadsafe`) or executes it using `asyncio.run`.
3. `sanitize_for_telegram_html(text: str)`: Converts Markdown headings, bold (`**text**`), monospace (`` `text` ``), and code blocks (` ```python ... ``` `) into Telegram-compatible HTML tags (`<b>`, `<code>`, `<pre>`).

### Alert Message Design
We format failure messages in standard Markdown. Since `notifier.py` already includes HTML sanitization, formatting remains clean:
```python
from notifier import send_telegram_message

def alert_test_failure(failure: dict):
    message = (
        f"❌ **Auto-Test Failure Detected!**\n\n"
        f"**Test**: `{failure['test_name']}`\n"
        f"**File**: `{failure['file_path']}:{failure['line_no']}`\n"
        f"**Error**: `{failure['error_message']}`\n\n"
        f"**Traceback**:\n"
        f"```python\n{failure['short_traceback']}\n```"
    )
    send_telegram_message(message)
```
This formats the error and traceback codeblock correctly on the user's Telegram client.

---

## 3. Log File Placement (`test_runs.log`)

The `test_runs.log` file should be placed in `nerves/workers/trading/test_runs.log`. This matches the directory location of `trades.log` and keeps the service files unified.

### Dedicated Logger Implementation
To keep test runs separate from the main trade execution logs in `trades.log` (which are written by the root logger), we instantiate a dedicated logger specifically for test runs in a unified alerting module.

```python
import logging
from pathlib import Path

# Resolve path relative to notifier / config location
LOG_PATH = Path(__file__).parent / "test_runs.log"

test_runs_logger = logging.getLogger("test_runs")
test_runs_logger.setLevel(logging.INFO)
test_runs_logger.handlers = []  # Prevent duplicate handlers on re-imports

file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
test_runs_logger.addHandler(file_handler)
```

---

## 4. Alerting Hooks: Watcher Test Runner & Health Check Scheduler

We propose a unified module, `nerves/workers/trading/alert_manager.py`, which acts as the central interface for handling test results and system health checks. 

Since the watcher (R1) is a standalone command-line tool, and health checks (R2) run within APScheduler (FastAPI event-loop thread), the module must support both synchronous and asynchronous operations.

### Proposed database helper for settings updates
The watcher runner may not have an active asyncio loop when updating statuses. Thus, we implement synchronous sqlite3 write capabilities for setting statuses in `trades.db`.
```python
def set_setting_sync(key: str, value: str) -> None:
    import sqlite3
    import config
    try:
        with sqlite3.connect(config.DB_PATH) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, value)
            )
            conn.commit()
    except Exception as e:
        print(f"Failed to save setting {key} = {value}: {e}")
```

### Proposed centralized Alert Manager (`alert_manager.py`)
```python
import datetime
from alert_manager_logger import test_runs_logger, set_setting_sync
from notifier import send_telegram_message

def handle_test_results(success: bool, failures: list, total_count: int):
    """
    Called by the Watcher Test Runner (R1) after executing pytest.
    """
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not success:
        # 1. Log to test_runs.log
        test_runs_logger.error(f"Test Run FAILED: {len(failures)}/{total_count} tests failed.")
        for f in failures:
            test_runs_logger.error(
                f"Test: {f['test_name']} in {f['file_path']}:{f['line_no']}\n"
                f"Error: {f['error_message']}\n"
                f"Traceback:\n{f['short_traceback']}\n"
                f"{'-'*40}"
            )
            
        # 2. Update dashboard status settings in trades.db
        set_setting_sync("test_runner_status", "failed")
        set_setting_sync("test_runner_last_run", now_str)
        
        summary_error = f"{len(failures)} failed: " + ", ".join([f["test_name"] for f in failures[:3]])
        if len(failures) > 3:
            summary_error += "..."
        set_setting_sync("test_runner_error", summary_error)
        
        # 3. Alert via Telegram
        for f in failures:
            alert_test_failure(f)
    else:
        # Success log
        test_runs_logger.info(f"Test Run PASSED: All {total_count} tests executed successfully.")
        
        # Update dashboard settings to OK
        set_setting_sync("test_runner_status", "passed")
        set_setting_sync("test_runner_last_run", now_str)
        set_setting_sync("test_runner_error", "")


def handle_health_results(status: str, failed_services: list):
    """
    Called by the Health Check Scheduler (R2) after system verification checks.
    """
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if status != "healthy":
        # 1. Log failure
        test_runs_logger.warning(f"Health Check Status: {status.upper()} | Failed: {', '.join(failed_services)}")
        
        # 2. Update dashboard settings
        set_setting_sync("health_status", status)
        set_setting_sync("health_last_check", now_str)
        set_setting_sync("health_error", f"Failed: {', '.join(failed_services)}")
        
        # 3. Alert via Telegram
        msg = (
            f"⚠️ **System Health Alert: {status.upper()}**\n\n"
            f"The following services are offline or failed verification:\n" + 
            "\n".join([f"• `{s}`" for s in failed_services]) + "\n\n"
            f"Please inspect the control panel."
        )
        send_telegram_message(msg)
    else:
        # Health check passed
        set_setting_sync("health_status", "healthy")
        set_setting_sync("health_last_check", now_str)
        set_setting_sync("health_error", "")
```

---

## 5. Dashboard Integration & Exposing Status API

To render the error/failure status on the dashboard, we integrate these settings into the FastAPI aggregator endpoint and frontend.

### FastAPI Status Endpoint Update
In `nerves/workers/trading/main.py`, update `system_status_endpoint()` to query settings:
```python
@app.get("/api/system/status")
async def system_status_endpoint():
    # Existing code for Server, MCP, RAG, etc.
    
    # Fetch test runner status
    test_runner_status = await database.get_setting("test_runner_status", "unknown")
    test_runner_last_run = await database.get_setting("test_runner_last_run", "never")
    test_runner_error = await database.get_setting("test_runner_error", "")

    # Fetch health check status
    health_status = await database.get_setting("health_status", "unknown")
    health_last_check = await database.get_setting("health_last_check", "never")
    health_error = await database.get_setting("health_error", "")

    return {
        # Existing values...
        "test_runner": {
            "status": test_runner_status,
            "last_run": test_runner_last_run,
            "error": test_runner_error
        },
        "health": {
            "status": health_status,
            "last_check": health_last_check,
            "error": health_error
        }
    }
```

### Dashboard Javascript UI Update
In `nerves/workers/trading/static/js/dashboard-core.js`, inside `loadSystemStatus()`, append two cards to `statusGrid.innerHTML`:

```javascript
  const tr = data.test_runner || { status: 'unknown', last_run: 'never' };
  const hl = data.health || { status: 'unknown', last_check: 'never' };

  grid.innerHTML += `
    <div class="status-card">
      <div class="status-card-icon">🧪</div>
      <div class="status-card-body">
        <div class="status-card-name">Auto-Test Runner</div>
        <div class="status-card-val ${tr.status === 'passed' ? 'status-ok' : tr.status === 'failed' ? 'status-err' : 'status-warn'}">
          ${tr.status.toUpperCase()} (Last: ${tr.last_run})
          ${tr.error ? `<br><span style="color:var(--sell);font-size:0.7rem">${tr.error}</span>` : ''}
        </div>
      </div>
    </div>
    <div class="status-card">
      <div class="status-card-icon">🏥</div>
      <div class="status-card-body">
        <div class="status-card-name">System Health</div>
        <div class="status-card-val ${hl.status === 'healthy' ? 'status-ok' : 'status-err'}">
          ${hl.status.toUpperCase()} (Last: ${hl.last_check})
          ${hl.error ? `<br><span style="color:var(--sell);font-size:0.7rem">${hl.error}</span>` : ''}
        </div>
      </div>
    </div>
  `;
```

This completes the full cycle of R3, integrating cleanly with the rest of the application without disrupting the existing framework.
