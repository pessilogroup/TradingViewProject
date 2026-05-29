# Handoff Report — TradingView Edge Node Evaluation

This report summarizes the read-only investigation and evaluation of the TradingView Edge Node ecosystem workspace.

## 1. Observation

### Webhook & Signal Processor Unit and Integration Tests
We located the following test files covering Webhook authentication/authorization, rate limiting, timeframe circuit breakers, and Telegram notifications under `nerves/workers/trading/tests/`:
- **Webhook Authentication / Authorization & Rate Limiting**:
  - File: `nerves/workers/trading/tests/unit/test_webhook_gateway.py`
  - Tests found:
    - `test_webhook_auth_via_body_secret` (Lines 11-25)
    - `test_webhook_auth_via_header` (Lines 27-41)
    - `test_webhook_unauthorized_wrong_secret` (Lines 49-61)
    - `test_rate_limit_blocks_after_15_requests` (Lines 83-104)
    - `test_rate_limit_resets_after_window` (Lines 106-126)
- **Timeframe Circuit Breakers / Verification**:
  - File: `nerves/workers/trading/tests/unit/test_signal_processor.py`
  - Tests found:
    - `test_valid_timeframes_pass` (Lines 77-84, parameterized with 60, "1h", "60m")
    - `test_invalid_timeframes_rejected` (Lines 86-97, parameterized with "4h", "15", "D", "1d", "240", "")
- **Telegram Notifications & Interactive Approvals**:
  - File: `nerves/workers/trading/tests/unit/test_telegram_bot_p8.py`
  - Tests found:
    - `test_send_interactive_trade_approval_returns_list` (Lines 22-38)
    - `test_send_interactive_trade_approval_returns_chat_message_pairs` (Lines 58-79)
    - `test_approval_timeout_manager_track_message` (Lines 94-106)
    - `test_approval_timeout_manager_check_cycle_expires` (Lines 108-144)
    - `test_telegram_sender_send_message_broadcasts` (Lines 81-87)

We ran the test suite using the command `pytest nerves/workers/trading/tests/` and observed 100% test completion with all 358 tests passing successfully:
```
====================== 358 passed, 3 warnings in 35.40s =======================
```

---

### Chrome DevTools Protocol (CDP) & Port 9222 Configuration

We examined how the Chrome DevTools Protocol (CDP) connection to TradingView is configured:
1. **PowerShell Launch Script**:
   - File: `scripts/launch_tv_msix_cdp.ps1`
   - Command args used to launch TradingView.exe (Lines 29-30):
     ```powershell
     -Command "TradingView.exe" `
     -Args "--remote-debugging-port=9222" `
     ```
   - Connection validation (Line 39):
     ```powershell
     Invoke-WebRequest -Uri "http://localhost:9222/json/version" -TimeoutSec 2
     ```
2. **Node.js MCP Server Connection**:
   - File: `tradingview-mcp/src/connection.js`
   - Port setting (Line 6):
     ```javascript
     const CDP_PORT = 9222;
     ```
   - Target list resolution (Lines 90-96):
     ```javascript
     async function findChartTarget() {
       const resp = await fetch(`http://${CDP_HOST}:${CDP_PORT}/json/list`);
       const targets = await resp.json();
       // Prefer targets with tradingview.com/chart in the URL
       return targets.find(t => t.type === 'page' && /tradingview\.com\/chart/i.test(t.url))
         || targets.find(t => t.type === 'page' && /tradingview/i.test(t.url))
         || null;
     }
     ```
   - Tab client instantiation (Line 73):
     ```javascript
     client = await CDP({ host: CDP_HOST, port: CDP_PORT, target: target.id });
     ```
3. **Python Client Wrapper**:
   - File: `nerves/workers/trading/mcp_client.py`
   - Initialized `self.cdp_port` from `config.MCP_CDP_PORT` (Default: `9222`).
   - Run command sets environment variable `TV_CDP_PORT` (Lines 71-72):
     ```python
     cwd=str(_MCP_DIR),
     env={**os.environ, "TV_CDP_PORT": str(self.cdp_port)}
     ```
   - However, running the client's health check failed with:
     ```
     Checking health...
     {'connected': False, 'cdp_port': 9222, 'mcp_cli_found': False, 'error': 'TradingView MCP not found at C:\\Users\\pesil\\working\\mj_trading\\TradingViewProject\\nerves\\workers\\tradingview-mcp\\src\\cli\\index.js. Run: git submodule update --init tradingview-mcp && cd tradingview-mcp && npm install'}
     ```
   - The path is constructed in `mcp_client.py` (Line 20) as:
     ```python
     _MCP_DIR = Path(__file__).parent.parent / "tradingview-mcp"
     ```
     Because `__file__` resolves to `C:\Users\pesil\working\mj_trading\TradingViewProject\nerves\workers\trading\mcp_client.py`, `_MCP_DIR` resolves to `C:\Users\pesil\working\mj_trading\TradingViewProject\nerves\workers\tradingview-mcp`. However, the submodule is actually cloned at the workspace root: `C:\Users\pesil\working\mj_trading\TradingViewProject\tradingview-mcp`.

---

### Return Type Verification (SCAR-G2-001)

We verified `send_interactive_trade_approval` and its callers to guarantee return contract compliance:
1. **Definition Signature**:
   - File: `nerves/workers/trading/telegram_bot.py` (Lines 50-61):
     ```python
     async def send_interactive_trade_approval(
         signal_id: int, message: str
     ) -> list:
     ```
     The docstring specifies:
     ```
     Returns:
         List[Tuple[int, int]]: List of (chat_id, message_id) for successfully sent messages.
         Empty list means failure / bot not running.
     ```
   - Return behavior (Lines 89, 96):
     ```python
     results.append((int(chat_id), msg.message_id))
     ...
     return results
     ```
2. **Caller Site**:
   - File: `nerves/workers/trading/hub/notification_hub.py` (Lines 249-261):
     ```python
     sent_pairs = await telegram_bot.send_interactive_trade_approval(
         signal_id=event.signal_id,
         message=msg,
     )
     if not sent_pairs:
         # Fallback to normal notify if bot not running
         await notifier.notify_all(msg + "\n\n*(Bot chưa bật, không thể dùng nút bấm duyệt lệnh)*")
     else:
         # REQ7: Register sent messages with ApprovalTimeoutManager for auto-timeout
         timeout_mgr = telegram_bot.get_approval_timeout_mgr()
         if timeout_mgr and isinstance(sent_pairs, list):
             for chat_id, message_id in sent_pairs:
                 timeout_mgr.track_message(event.signal_id, chat_id, message_id)
     ```
3. **Regression Test Guard**:
   - File: `nerves/workers/trading/tests/unit/test_telegram_bot_p8.py` (Lines 22-38) asserts that `send_interactive_trade_approval` returns a `list` to satisfy `SCAR-G2-001`.

---

## 2. Logic Chain

1. **Webhook / Signal / Notification Unit and Integration Tests**:
   - We ran `pytest nerves/workers/trading/tests/` which runs the unit, integration, and E2E tests.
   - The test reports showed `358 passed`, and we inspected the test code to verify that Webhook auth (`test_webhook_auth_via_body_secret`), rate limiting (`test_rate_limit_blocks_after_15_requests`), timeframe circuit breakers (`test_invalid_timeframes_rejected`), and Telegram notifications (`test_telegram_sender_send_message_broadcasts`) are covered.
   - Therefore, the test infrastructure is robustly verifying these components.

2. **CDP Connection Configuration and Port Compatibility**:
   - `scripts/launch_tv_msix_cdp.ps1` runs the Windows Store (MSIX) packaging launcher specifying `--remote-debugging-port=9222`.
   - `tradingview-mcp/src/connection.js` hardcodes `const CDP_PORT = 9222;` and resolves tabs via local fetch to `http://localhost:9222/json/list`.
   - Since `CDP_PORT` is defined as a constant inside the Node.js server core modules (`connection.js`, `tab.js`) and is not overridden via environment variables or CLI flags for target tracking, the current MCP stack is hard-locked to port `9222`. Any configuration trying to launch TradingView on a different port will fail to establish a CDP websocket connection.

3. **Path Mismatch Bug**:
   - `mcp_client.py` sets `_MCP_DIR = Path(__file__).parent.parent / "tradingview-mcp"`.
   - `Path(__file__)` is `nerves/workers/trading/mcp_client.py`, so `parent.parent` is `nerves/workers`.
   - The resulting path is `nerves/workers/tradingview-mcp`, which does not exist.
   - The actual `tradingview-mcp` is at the root directory of the workspace.
   - Therefore, executing the client (e.g. via `test_cdp.py`) yields a `RuntimeError` claiming `TradingView MCP not found`.

4. **Return Type Mismatch (SCAR-G2-001)**:
   - `telegram_bot.py`'s `send_interactive_trade_approval` returns `results` (which is a list of tuples containing chat/message IDs).
   - `notification_hub.py` verifies `isinstance(sent_pairs, list)` and successfully loops over it: `for chat_id, message_id in sent_pairs`.
   - Therefore, there is no type mismatch, and `ApprovalTimeoutManager.track_message` receives the correct types.

---

## 3. Caveats

- **No Windows MSIX Live Execution**: We did not execute the MSIX launcher script (`scripts/launch_tv_msix_cdp.ps1`) or spin up a live browser session as we do not have a desktop/GUI context in this execution environment.
- **Submodule State**: We assumed the submodule `tradingview-mcp` is properly checked out at the root. We confirmed its presence and file layout via reading directories and searching files.

---

## 4. Conclusion

- **SCAR-G2-001 Return Type**: Fully compliant. The return contract has been fixed and successfully guarded with regression tests in `test_telegram_bot_p8.py`.
- **CDP Port**: Strictly port `9222`. The Node.js application `tradingview-mcp` has hardcoded dependencies on port `9222` for the connection and tab resolution layers.
- **Path Mismatch Bug**: There is an active bug in `nerves/workers/trading/mcp_client.py` line 20. The path must be resolved using `Path(__file__).parent.parent.parent.parent / "tradingview-mcp"` or relative to the workspace root.
- **Test Suitability**: Webhook auth, rate limiting, timeframe circuit breaking, and notification flows are covered extensively by unit/integration tests with a 100% pass rate.

### Proposed Code Changes (Patch)

To fix the path mismatch in `nerves/workers/trading/mcp_client.py`:

```diff
--- nerves/workers/trading/mcp_client.py
+++ nerves/workers/trading/mcp_client.py
@@ -20,1 +20,1 @@
-_MCP_DIR = Path(__file__).parent.parent / "tradingview-mcp"
+_MCP_DIR = Path(__file__).parent.parent.parent.parent / "tradingview-mcp"
```

---

## 5. Verification Method

To verify the conclusions independently:
1. **Path mismatch verification**:
   - Run the script `python nerves/workers/trading/scripts/test_cdp.py`.
   - Observe the error: `error: TradingView MCP not found at C:\...\nerves\workers\tradingview-mcp\src\cli\index.js`.
   - Apply the patch above, rerun `test_cdp.py`, and check that the path error is gone (it will attempt to connect to port 9222, confirming the path mismatch is resolved).
2. **Pytest verification**:
   - Run `pytest nerves/workers/trading/tests/` to run all unit, integration, and E2E tests, verifying that the entire test suite passes.
3. **CDP Port verification**:
   - Examine `tradingview-mcp/src/connection.js` lines 5-6 and note the hardcoded port constant.
