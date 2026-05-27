# Handoff Report: Watcher-Based Auto-Test Execution

## 1. Observation

- **Dependency Inspection:** 
  - Checked `nerves/workers/trading/requirements-test.txt`, confirming pytest dependencies:
    ```
    1: pytest>=9.0
    2: pytest-asyncio>=1.3
    ```
  - Attempted to import `watchdog` via `python -c "import watchdog"`, which failed:
    ```
    Traceback (most recent call last):
      File "<string>", line 1, in <module>
    ModuleNotFoundError: No module named 'watchdog'
    ```
  - Executed `pip list` in background task `f4d6bd27-3b5b-45c3-ab4b-f2bf19dca249/task-23`. The output confirmed `watchfiles 1.1.1` and `pytest 9.0.3` are installed.
- **Directory Structure:**
  - Ran `find_by_name` on `pine/` and `nerves/workers/trading/`, confirming folders exist and hold code and test files (e.g., `nerves/workers/trading/pytest.ini`, `nerves/workers/trading/tests/`).
- **Pytest Verification:**
  - Executed `python -m pytest tests/unit/test_ai_analyzer.py` inside `nerves/workers/trading/` (task `task-52`), which succeeded with:
    ```
    tests/unit/test_ai_analyzer.py::test_cooldown_rejects_duplicate PASSED   [ 33%]
    tests/unit/test_ai_analyzer.py::test_signal_processor_emits_alert_triggered PASSED [ 66%]
    tests/unit/test_ai_analyzer.py::test_high_confidence_triggers_trade PASSED [100%]

    ============================== 3 passed in 0.69s ==============================
    ```

---

## 2. Logic Chain

1. **Available Libraries:** Since `watchdog` is not installed, but `watchfiles` v1.1.1 is available, `watchfiles` is the optimal library for event-driven filesystem watching. A custom polling implementation using `os.walk` + `os.stat` is also feasible and provides a zero-dependency fallback.
2. **Pytest Execution Method:** Standard programmatic execution via `pytest.main()` caching modules in `sys.modules` prevents modified code from being reloaded. Therefore, launching `pytest` as a subprocess via `sys.executable -m pytest` is mandatory to guarantee new changes are loaded.
3. **Debounce Logic:** Using an async event consumer with a queue (`asyncio.Queue`) allows the system to easily drain overlapping file-change bursts, recalculate settling time, and execute a single test runner run once the filesystem becomes quiet for >= 1.0 second.
4. **Script Location:** Placing the tool at `nerves/workers/trading/scripts/autotest_watcher.py` keeps it grouped with existing helper scripts and is in the correct working directory to run pytest natively.

---

## 3. Caveats

- **Operating System Locks:** On Windows, file-writing IDEs or compilers might temporarily lock files. The watcher must gracefully handle `PermissionError` / `OSError` during `stat` or read checks.
- **Pine Script Limitations:** Modifying Pine scripts under `pine/` will trigger the test suite, but Pine Script cannot be executed natively by Python/pytest. The tests will only check Python-side loaders or mocks that ingest Pine scripts.
- **Excluded Patterns:** If files under `.venv` or `.git` are changed, they could trigger test loops if not carefully pruned. The script explicitly includes an exclusion set.

---

## 4. Conclusion

The auto-test execution watcher should be implemented as an asynchronous daemon using `watchfiles.awatch` with a standard-library polling fallback (`PollingWatcher`). The debounce mechanism must use an `asyncio.Queue` draining system with a 1.0-second delay. Pytest must be invoked in a separate subprocess. The runner should reside at `nerves/workers/trading/scripts/autotest_watcher.py`.

---

## 5. Verification Method

To verify the strategy and implementation:
1. **Runner Launch:** Run the watcher script:
   ```powershell
   python nerves/workers/trading/scripts/autotest_watcher.py
   ```
2. **File Change Trigger:** Modify a file in `nerves/workers/trading/` (e.g. append a newline to `main.py`) or in `pine/` and check if the console detects the event, waits for 1 second, and executes `pytest` successfully.
3. **Double-Save Debounce Trigger:** Save a file multiple times within 0.5s; verify that pytest is run only **once** after a 1.0-second quiet period.
