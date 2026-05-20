## 2026-05-21T04:31:17Z

Implement a version checking and warning mechanism for `angati.exe` inside the `TradingViewProject` workspace when the hook server starts.

Working directory: c:\Users\pesil\working\mj_trading\TradingViewProject
Integrity mode: development

## Requirements

### R1. Boot-time Version Checking
On startup of the hook service, compare the local `angati.exe` binary with the main Antigravity Brain's `angati.exe` (found under the App Data Directory `C:\Users\pesil\.gemini\antigravity\tools\angati` or similar).

### R2. Non-blocking Warning Output
If a version mismatch is detected, print a warning to `stderr` requesting the user to manually restart the server to synchronize the binary. The check must be completely non-blocking and not interfere with the startup of the SRA Hook Server.

### R3. Automated Testing
Extend `test_angati_integration.py` or add a unit test to verify that the version checking logic triggers correctly when the files differ (using a temporary mock mismatch file) and handles missing files gracefully.

## Acceptance Criteria

### Boot Validation
- [ ] Startup logs include a version check status.
- [ ] If the local file matches the main Brain binary, no action or a normal status message is printed.
- [ ] If a mismatch is detected, a prominent warning is printed to `stderr` indicating the files differ.

### Test Coverage
- [ ] Test suite executes successfully with `python -m unittest` or the integration runner.
- [ ] The test confirms that a mismatched version triggers the stderr warning.
