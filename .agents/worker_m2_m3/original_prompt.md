## 2026-05-20T21:36:20Z

Objective: Implement the version checking and warning mechanism for `angati.exe` when the hook server starts, and add automated tests to verify it.

Files to modify:
1. `nerves/core/hook_service.py`
2. `nerves/workers/trading/test_angati_integration.py`

Requirements for hook_service.py:
- Add a helper function `check_angati_version_async()` that runs asynchronously in a daemon thread.
- Dynamically resolve local and brain `angati.exe` paths:
  * Local path candidates: check `os.environ.get("ANGATI_LOCAL_EXE_PATH")`, `AGENTS_ROOT / "tools" / "angati" / "angati.exe"`, and `AGENTS_ROOT / "angati.exe"`.
  * Brain path candidates: check `os.environ.get("ANGATI_BRAIN_EXE_PATH")`, `Path.home() / "EAIS" / "test_scaffold" / "angati.exe"`, `Path.home() / "EAIS" / "spine" / "angati" / "angati.exe"`, and `Path.home() / ".gemini" / "antigravity" / "tools" / "angati" / "angati.exe"`.
- If either file is missing, exit silently (no crash, no warning).
- Compute SHA-256 hashes of both files using a chunked reader (e.g. 64KB chunks or 8KB chunks) to prevent loading large files in memory.
- If hashes differ, print a prominent warning to sys.stderr:
  `[SRA Server] WARNING: Local angati.exe version mismatch detected! Please manually restart the hook server to synchronize the binary.`
- Call `check_angati_version_async()` on startup inside `main()`.

Requirements for test_angati_integration.py:
- Add 3 unittest test cases to the `TestAngatiIntegration` class or as a new test class:
  * `test_angati_version_mismatch_warning`: Tests that a mismatch triggers the stderr warning (use environment overrides with temporary mock mismatch files).
  * `test_angati_version_matching`: Tests that identical file hashes trigger no warning.
  * `test_angati_version_missing_files`: Tests that missing file conditions are handled gracefully and silently (no warnings or crashes).
- Make sure to close mock file handles and delete temporary files in a `finally` block to avoid Windows file lock issues (PermissionError).
- Capture `sys.stderr` via redirect_stderr to assert the warning message.

Run tests:
- Execute the test suite using `python -m unittest nerves/workers/trading/test_angati_integration.py` or pytest. Ensure the new test cases run successfully and print passing indicators.

Write a handoff:
- Save your handoff report to `handoff.md` in your working directory `c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\worker_m2_m3`. In the report, document the exact changes made, the test results, and command output proving the tests pass.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.
