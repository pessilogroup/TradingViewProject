# Watcher-Based Auto-Test Execution Strategy Report

## Executive Summary
This report analyzes the implementation strategy for a watcher-based auto-test execution system (R1) designed to monitor `nerves/workers/trading/` (for `.py` changes) and `pine/` (for `.pine` changes) in the workspace. The runner must run `pytest` automatically with a debounce time of at least 1.0 second. 

Based on codebase analysis, the `watchfiles` (v1.1.1) library is already installed in the environment. An asynchronous queue-based event debouncer combined with a `subprocess`-based `pytest` invocation is the recommended design because it circumvents Python's standard `sys.modules` caching issues.

---

## 1. Library Availability & Feasibility

We evaluated two main options for file monitoring in the target environment:

### Option A: `watchfiles` (v1.1.1)
- **Status:** Installed in the Python environment (discovered via `pip list` in task `task-23`).
- **Mechanism:** Leverages a high-performance Rust backend to intercept OS-level file system events (`ReadDirectoryChangesW` on Windows).
- **Pros:**
  - Extremely low CPU and memory overhead compared to polling.
  - Native support for asynchronous monitoring via `awatch()`.
  - Filter classes and function paths can ignore patterns (`__pycache__`, `.venv`, `.git`, etc.) effortlessly.
- **Cons:** Binary dependency (already resolved in this environment).

### Option B: Custom File Polling
- **Status:** Feasible using Python's standard library (`os.walk` + `os.stat` + `time.sleep`).
- **Mechanism:** Walks the target directories at regular intervals (e.g., every 500ms) comparing file sizes and modification times (`st_mtime`).
- **Pros:**
  - Zero dependencies, pure Python.
  - Portable across any environment without installation issues.
- **Cons:**
  - Performs CPU-bound disk directory scans.
  - Scales poorly if the file count grows (currently ~145 files total, so overhead is negligible but still higher than `watchfiles`).

### Recommendation
**Use `watchfiles.awatch`** since it is already installed, highly performant, and maps directly to Python's async event loop. We will provide a pure-Python fallback option (custom polling) inside the runner script to handle environments where `watchfiles` binary compilation might fail or get removed.

---

## 2. Debounce Mechanism Design

A debounce delay of at least 1.0 second is required to avoid triggering pytest multiple times in rapid succession (e.g., when a user saves multiple files, when auto-formatters run, or when a branch checkout modifies many files).

### Recommended Design: Async Queue-Based Debouncer
Using `asyncio.Queue` combined with `watchfiles.awatch` provides a clean, single-threaded, concurrent design:

1. **Producer Loop:** Listens to file changes via `awatch`. When changes occur, it filters for `.py` and `.pine` files (excluding `.venv`, `.git`, `.agents`, `__pycache__`). If any are relevant, it pushes them into an `asyncio.Queue`.
2. **Consumer Loop:** 
   - Wakes up when a new item is available in the queue.
   - Sets a `last_change` timestamp.
   - Continuously drains any additional items from the queue (updating the timestamp).
   - Enters a loop sleeping for the `remaining` debounce window.
   - If new items arrive during the sleep, it drains them and resets the timer (extending the debounce).
   - Once 1.0 second has passed without any new events, it triggers the pytest execution.

#### Debounce Code Logic (Async):
```python
import asyncio
import time

class AsyncDebouncer:
    def __init__(self, callback, delay=1.0):
        self.callback = callback
        self.delay = delay
        self.queue = asyncio.Queue()
        self.last_change = 0.0

    async def add_event(self, path):
        await self.queue.put(path)

    async def start(self):
        while True:
            # Wait for first event
            _ = await self.queue.get()
            self.last_change = time.time()

            # Drain immediate duplicates
            while not self.queue.empty():
                self.queue.get_nowait()
                self.last_change = time.time()

            # Cooldown settling loop
            while True:
                now = time.time()
                elapsed = now - self.last_change
                remaining = self.delay - elapsed
                if remaining <= 0:
                    break
                await asyncio.sleep(remaining)
                # If new events arrived during sleep, update timestamp and continue waiting
                if not self.queue.empty():
                    while not self.queue.empty():
                        self.queue.get_nowait()
                    self.last_change = time.time()

            # Trigger the test execution
            await self.callback()
            self.queue.task_done()
```

---

## 3. Pytest Execution Strategy

We analyzed two ways to invoke pytest: programmatically (`pytest.main()`) vs. via a subprocess (`subprocess.run`).

### Programmatic (`pytest.main()`)
- Calling `pytest.main(["tests/"])` runs tests within the same Python process.
- **The Module Caching Pitfall:** Python stores imported modules in `sys.modules`. Once a test file or source module is imported during the first test run, it remains cached. When a file is modified on disk, subsequent calls to `pytest.main()` **will run the old cached code**, not the modified file.
- **Mitigation:** One would have to purge all local modules from `sys.modules` before each test run, which is notoriously bug-prone and often causes import and database connection leakage issues.

### Subprocess (`subprocess.run`)
- Invoking `python -m pytest` creates a fresh operating system process.
- **Pros:**
  - Bypasses `sys.modules` caching entirely; Python loads the freshly saved code files from scratch.
  - Test runner process state is cleanly isolated; memory and database connection pools are cleanly closed.
  - Can easily kill/terminate a hanging or stuck test suite.
- **Cons:** Slight process-spawning overhead (approx. 50ms, negligible compared to pytest run time).

### Recommendation
**Execute pytest via a subprocess** using `sys.executable -m pytest`. Running via `sys.executable` ensures pytest runs with the exact same python interpreter and environment pathing configuration.

---

## 4. Test Runner Script Specification

### Script Location
We recommend placing the test runner script at:
`nerves/workers/trading/scripts/autotest_watcher.py`

This matches the existing convention of grouping scripts under `nerves/workers/trading/scripts/` (e.g. `test_cdp.py`, `test_screenshot.py`), keeping the parent workspace directories clean while remaining close to the code and tests.

### Script Implementation Draft

```python
"""
autotest_watcher.py
Watcher-based auto-test execution tool with debouncing.
Monitors: nerves/workers/trading/ and pine/ for changes in .py and .pine.
Triggers: pytest on change.
"""

import os
import sys
import time
import asyncio
import subprocess
from pathlib import Path

# Resolve workspace directories
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent # Resolve root from nerves/workers/trading/scripts/
MONITOR_DIRS = [
    PROJECT_ROOT / "nerves" / "workers" / "trading",
    PROJECT_ROOT / "pine"
]
PYTEST_CWD = PROJECT_ROOT / "nerves" / "workers" / "trading"

EXTENSIONS = {".py", ".pine"}
EXCLUDE_DIRS = {".git", "__pycache__", ".agents", ".venv", "venv", "node_modules", "cortex"}

def is_relevant_path(path_str: str) -> bool:
    path = Path(path_str)
    if path.suffix not in EXTENSIONS:
        return False
    # Check if path contains any excluded directory names
    for part in path.parts:
        if part in EXCLUDE_DIRS:
            return False
    return True

async def run_pytest():
    print("\n" + "="*80)
    print(f"[{time.strftime('%H:%M:%S')}] File changes settled. Triggering pytest...")
    print("="*80)

    try:
        # Run pytest inside the canonical environment folder
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pytest",
            cwd=str(PYTEST_CWD),
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        await process.wait()
        print(f"[{time.strftime('%H:%M:%S')}] Test run completed with exit code: {process.returncode}\n")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Error executing pytest: {e}\n")

# --- Fallback Polling Class ---
class PollingWatcher:
    def __init__(self, watch_dirs, debounce_delay=1.0):
        self.watch_dirs = [Path(d) for d in watch_dirs]
        self.debounce_delay = debounce_delay
        self.mtimes = {}

    def scan_files(self):
        files = {}
        for d in self.watch_dirs:
            if not d.exists():
                continue
            for root, dirs, filenames in os.walk(d):
                # In-place filtering to optimize directory walking
                dirs[:] = [dir_name for dir_name in dirs if dir_name not in EXCLUDE_DIRS]
                for filename in filenames:
                    file_path = Path(root) / filename
                    if is_relevant_path(str(file_path)):
                        files[file_path] = file_path
        return files

    async def run(self):
        # Initialize
        files = self.scan_files()
        for path in files:
            try:
                self.mtimes[path] = path.stat().st_mtime
            except OSError:
                pass

        print("Falling back to standard library file polling...")
        last_change = 0.0
        pending = False

        while True:
            await asyncio.sleep(0.5)
            current_files = self.scan_files()
            changed = False

            # Check additions & modifications
            for path, file_obj in current_files.items():
                try:
                    mtime = file_obj.stat().st_mtime
                    if path not in self.mtimes:
                        self.mtimes[path] = mtime
                        changed = True
                    elif self.mtimes[path] < mtime:
                        self.mtimes[path] = mtime
                        changed = True
                except OSError:
                    pass

            # Check deletions
            for path in list(self.mtimes.keys()):
                if path not in current_files:
                    del self.mtimes[path]
                    changed = True

            if changed:
                last_change = time.time()
                pending = True

            if pending and (time.time() - last_change >= self.debounce_delay):
                pending = False
                await run_pytest()

# --- Watchfiles Async Loop ---
async def run_watchfiles():
    from watchfiles import awatch

    queue = asyncio.Queue()
    debounce_delay = 1.0

    async def consumer():
        while True:
            _ = await queue.get()
            last_change = time.time()

            # Drain queue
            while not queue.empty():
                queue.get_nowait()
                last_change = time.time()

            # Wait and debounce
            while True:
                now = time.time()
                elapsed = now - last_change
                remaining = debounce_delay - elapsed
                if remaining <= 0:
                    break
                await asyncio.sleep(remaining)
                if not queue.empty():
                    while not queue.empty():
                        queue.get_nowait()
                    last_change = time.time()

            await run_pytest()
            queue.task_done()

    # Start consumer
    asyncio.create_task(consumer())

    # Watch producer
    watch_paths = [str(d) for d in MONITOR_DIRS if d.exists()]
    async for changes in awatch(*watch_paths):
        relevant_changes = [path for _, path in changes if is_relevant_path(path)]
        if relevant_changes:
            for r in relevant_changes:
                await queue.put(r)

async def main():
    print("="*60)
    print("Starting Watcher-Based Auto-Test Execution Runner")
    print(f"Monitored directories:")
    for d in MONITOR_DIRS:
        print(f"  - {d}")
    print(f"Pytest environment: {PYTEST_CWD}")
    print("="*60)

    try:
        import watchfiles
        await run_watchfiles()
    except ImportError:
        watcher = PollingWatcher(MONITOR_DIRS)
        await watcher.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nWatcher terminated by user.")
```

---

## 5. Deployment / Execution Service

To run this auto-test execution script as a reliable background worker, we can choose one of the following methods:

1. **Systemd Service (Recommended for Linux server deployments):**
   A template systemd unit file can be placed at `/etc/systemd/system/trading-autotest.service`:
   ```ini
   [Unit]
   Description=TradingView Project Auto-Test Watcher
   After=network.target

   [Service]
   Type=simple
   User=pesil
   WorkingDirectory=c:\Users\pesil\working\mj_trading\TradingViewProject\nerves\workers\trading
   ExecStart=python scripts/autotest_watcher.py
   Restart=on-failure
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

2. **Windows Startup / Background Execution:**
   On Windows, the process can be spun up as a background job via PowerShell:
   ```powershell
   Start-Process python -ArgumentList "nerves/workers/trading/scripts/autotest_watcher.py" -WindowStyle Hidden
   ```
   Or registered as a scheduled task trigger or managed daemon under the local Go-native controller.
