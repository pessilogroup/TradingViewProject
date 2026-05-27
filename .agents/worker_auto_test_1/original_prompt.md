## 2026-05-28T00:48:52Z
You are the Worker subagent. Your identity is 'worker_auto_test_1'.
Your working directory is 'c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\worker_auto_test_1'.
Your task is to implement the Watcher-Based Auto-Test Execution, System Health & Integration Verification, Multi-Channel Alerting, and API/UI Dashboard Extensions according to the plan described in:
'c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\teamwork_preview_orchestrator_auto_test\plan.md'

Please refer to the following Explorer handoff files for detailed strategy & analysis:
- Explorer 1 (R1): 'c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\explorer_auto_test_1\handoff.md'
- Explorer 2 (R2): 'c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\explorer_auto_test_2\handoff.md'
- Explorer 3 (R3): 'c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\explorer_auto_test_3\handoff.md'

Please perform the following implementations:
1. Create 'nerves/workers/trading/scripts/autotest_watcher.py' implementing:
   - Debounced watch (>= 1.0s) of 'nerves/workers/trading/' and 'pine/' for .py and .pine changes.
   - Primary: watchfiles.awatch. Fallback: custom PollingWatcher using os.stat/os.walk.
   - Run tests as a subprocess 'sys.executable -m pytest' from the 'nerves/workers/trading/' folder.
   - A background loop running every 30s that checks:
     a. sqlite DB connection (read & write using database.set_setting/get_setting).
     b. port 5000 (API Server) liveness via asyncio.open_connection.
     c. port 9222 (CDP) liveness via asyncio.open_connection.
   - Centralized status updates in DB settings table.
2. Implement 'nerves/workers/trading/alert_manager.py' containing the logic to:
   - Log failures/test runs to 'nerves/workers/trading/test_runs.log'.
   - Send Telegram Alerts on test failure or health state transition using the existing 'nerves/workers/trading/notifier.py'.
   - Extract filename/health check name and a shortened traceback (e.g. last 8 lines) for the Telegram message.
3. Update 'nerves/workers/trading/main.py' to return the new health and test runner statuses under '/api/system/status'.
4. Update 'nerves/workers/trading/static/js/dashboard-core.js' to fetch and render these health checks dynamically inside the dashboard statusGrid.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Once implementation is complete, run standard tests to verify the code works correctly, test the watcher manually, and document all command runs, outputs, and status checks in your handoff report 'handoff.md' in your folder. Then send a message back.
