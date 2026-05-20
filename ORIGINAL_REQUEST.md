# Original User Request

## Initial Request — 2026-05-21T04:31:17+07:00

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

## Follow-up — 2026-05-21T05:09:33+07:00

The goal of this project is to perform a comprehensive stability and safety evaluation of the TradingView Edge Node ecosystem, verifying runtime reliability, CDP browser automation connectivity, and Telegram notifications under stress and failure states.

Working directory: C:\Users\pesil\working\mj_trading\TradingViewProject

## Requirements

### R1. Webhook Edge Node Stability Verification
- Validate the FastAPI Edge Node webhook under high concurrency and boundary inputs (invalid price, format, token).
- Check that circuit breakers successfully isolate non-1H signals.

### R2. TradingView CDP & Browser Integration Audit
- Verify the connection to the TradingView Desktop app via Chrome DevTools Protocol (CDP) on port 9222.
- Perform sanity tests to check that indicator alerts and chart interfaces load correctly.

### R3. Telegram Notification & Interactive Hub Verification
- Audit the Telegram Bot service, ensuring message dispatch and interactive trade approvals return correctly structured message coordinates.
- Ensure no silent return type mismatches between components.

## Acceptance Criteria

### Security & Error Handling
- [ ] No unauthorized payloads bypass the webhook gate.
- [ ] Webhook rate limits (15 req/min) trigger HTTP 429 successfully and recover automatically.

### System Interoperability
- [ ] CDP debug connection returns valid version JSON from local TradingView desktop app.
- [ ] Interactive approval callbacks map accurately to their respective active signal trackers without silent failures.
