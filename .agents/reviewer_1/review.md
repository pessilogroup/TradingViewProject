# Review Report: Scan All Background Feature

**Verdict**: REQUEST_CHANGES

## 🔎 Scope of Review
The following files were inspected, linted, and verified:
1. `nerves/workers/trading/analysis.py` (REST scanner, rate limiting, concurrency, Weex adapter integration)
2. `nerves/workers/trading/main.py` (FastAPI lifespans, background tasks integration, `/api/scan/all` endpoint)
3. `nerves/workers/trading/telegram_bot.py` (`cmd_scan_all`, `cmd_scan_enhanced`, status, positions, and formatting)
4. `nerves/workers/trading/notifier.py` (HTML escaping logic via `sanitize_for_telegram_html`)

---

## 🛠️ Verification Execution

### Command Line Invocation (pytest)
```powershell
python -m pytest tests/unit/test_scan_all.py
```
- **Result**: 9 tests passed.
- **Log output**:
  ```
  tests/unit/test_scan_all.py::test_fetch_candles_weex_success PASSED      [ 11%]
  tests/unit/test_scan_all.py::test_fetch_candles_bybit_success PASSED     [ 22%]
  tests/unit/test_scan_all.py::test_fetch_candles_binance_success PASSED   [ 33%]
  tests/unit/test_scan_all.py::test_fetch_candles_rate_limited PASSED      [ 44%]
  tests/unit/test_scan_all.py::test_fetch_candles_failure_fallback PASSED  [ 55%]
  tests/unit/test_scan_all.py::test_scan_single_symbol_rest PASSED         [ 66%]
  tests/unit/test_scan_all.py::test_scan_all_configured_exchanges PASSED   [ 77%]
  tests/unit/test_scan_all.py::test_api_scan_all_endpoint PASSED           [ 88%]
  tests/unit/test_scan_all.py::test_telegram_cmd_scan_all PASSED           [100%]
  ============================== 9 passed in 4.49s ==============================
  ```

### Command Line Invocation (Ruff Linting)
```powershell
python -m ruff check nerves/workers/trading/analysis.py nerves/workers/trading/main.py nerves/workers/trading/telegram_bot.py
```
- **Result**: Failed with 21 formatting and style errors (lint detail in findings below).

---

## 📋 Dimension Analysis & Findings

### [Critical] Finding 1: INTEGRITY VIOLATION (Facade Fallback)
- **What**: In `nerves/workers/trading/analysis.py` (lines 397-398), when `fetch_candles_with_retry` fails after all retries (e.g. due to rate limiting or connection failure), it logs an error and returns mock candle data:
  ```python
  logger.error(f"Failed to fetch candles for {symbol} on {exchange_name} after {max_retries} attempts.")
  return generate_mock_candles(limit)
  ```
- **Where**: `nerves/workers/trading/analysis.py:397-398`
- **Why**: This is a facade implementation that masks real data failures. Instead of registering a proper error result for the symbol (e.g., `price=0.0`, `error="Failed to fetch data"`), the scanner calculates Trend Template and VCP setups based on 365 days of fake candles (price fixed at 100.5, volume at 1000.0). This generates incorrect scan metrics and hides failures from the user, violating system integrity.
- **Suggestion**: Raise a connection/data exception or return an empty list `[]` to allow `scan_single_symbol_rest` to catch it and cleanly output a `ScanResult` with an error message (like `"Failed to fetch candles"`), rather than using a mock data facade.

### [Major] Finding 2: HTML-Escaping Bugs in Telegram Bot Commands
- **What**: `sanitize_for_telegram_html` in `notifier.py` begins by escaping all HTML special characters:
  ```python
  text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
  ```
  However, `cmd_scan_all` and `cmd_scan_enhanced` in `telegram_bot.py` build their output messages using standard HTML tags:
  ```python
  lines = [f"📊 <b>Kết quả Scan All</b>\n"]
  lines.append("<pre>")
  ...
  text = sanitize_for_telegram_html("\n".join(lines))
  ```
  Because they pass strings containing standard HTML tags (`<b>`, `<pre>`, `<code>`) directly into `sanitize_for_telegram_html`, the escaping step converts those tags into `&lt;b&gt;`, `&lt;pre&gt;`, `&lt;code&gt;`. When sent to Telegram, these tags are displayed as literal text instead of rendering styled HTML format.
- **Where**: `nerves/workers/trading/telegram_bot.py` (`cmd_scan_all`, `cmd_scan_enhanced`, `cmd_status`, `cmd_positions`, `cmd_trades`, `cmd_report`, `cmd_balance_enhanced`, `send_interactive_trade_approval`, and `TelegramSender.send_message`).
- **Why**: Breaks all Telegram interface formatting, displaying raw HTML code tags to the user.
- **Suggestion**: Re-design the formatting pipeline: either build messages using Markdown and let `sanitize_for_telegram_html` convert them to HTML, or avoid running `sanitize_for_telegram_html` on messages already pre-formatted as HTML (only sanitize dynamic content/inputs like symbol or error names).

### [Major] Finding 3: Syntax and Style Issues (21 Ruff Errors)
- **What**: Ruff check identified 21 errors across the modified files:
  - **F541 (Extraneous f-string prefix)**: `analysis.py` lines 305, 309, 371.
  - **E741 (Ambiguous variable name)**: `analysis.py` line 448 (using lowercase `l` as variable name).
  - **F401 (Unused imports)**: `main.py` line 5 (`secrets`), line 41 (`SignalReceived`), and `telegram_bot.py` line 1873 (`config`).
  - **E402 (Module level import not at top of file)**: `main.py` lines 40, 41, 44, 275, 279, and `telegram_bot.py` lines 1143, 1144.
  - **E401 (Multiple imports on one line)**: `main.py` line 52 (`import sys, io`).
  - **E722 (Bare except)**: `main.py` line 108 (`except:`).
  - **E701 (Multiple statements on one line)**: `telegram_bot.py` line 1015 (`if c: confidences.append(c)`).
  - **F841 (Local variable assigned but unused)**: `telegram_bot.py` line 1396 (`except Exception as e:`).
- **Where**: `analysis.py`, `main.py`, `telegram_bot.py`
- **Why**: Violates formatting guidelines and can cause runtime ambiguity (e.g. ambiguous `l` and bare `except:` catching system exit signals).
- **Suggestion**: Correct code styling and imports to resolve all 21 Ruff linting errors.

### [Minor] Finding 4: Sequential Exchange Scanning (Bottleneck)
- **What**: In `scan_all_configured_exchanges`, the scanner iterates over each exchange sequentially:
  ```python
  for eid in exchange_ids:
      ...
      if tasks:
          exchange_results = await asyncio.gather(*tasks)
  ```
- **Where**: `nerves/workers/trading/analysis.py:548-582`
- **Why**: If one exchange has slow REST responses, it blocks the start of the scan on the next exchange.
- **Suggestion**: Gather all tasks across all exchanges concurrently using `asyncio.gather` on a single flattened list of tasks, rather than looping sequentially at the exchange level.

### [Minor] Finding 5: Concurrent Scan UX Race Condition
- **What**: If `/scan_all` is triggered via Telegram while a background scan is already in progress, `scan_all_configured_exchanges` returns `_latest_scan_results` instantly.
- **Where**: `nerves/workers/trading/analysis.py:530-532` & `telegram_bot.py:842`
- **Why**: If a user runs `/scan_all` twice, the second invocation completes instantly with stale results from the previous run (or an empty list if it's the first run), which may confuse users.
- **Suggestion**: If a scan is running, either let the caller wait (`await` the current running task) or reply with an explicit warning: "A scan is already in progress, please check back in a few seconds."

---

## ⚡ Adversarial Critic Report (Stress-Testing)

**Overall Risk Assessment**: HIGH

### 1. Assumption Stress-Testing: Rate-Limit Handlers under Severe Congestion
- **Assumption Challenged**: That `resp.headers.get("Retry-After")` is a valid, parseable float representation of seconds.
- **Attack Scenario**: An exchange rate-limits the client and returns a standard HTTP date representation (e.g. `Retry-After: Wed, 21 Oct 2015 07:28:00 GMT`) or an empty header `Retry-After: `.
- **Blast Radius**: `float(resp.headers.get("Retry-After", 1.0))` throws a `ValueError`. The attempt fails, falls into the general `except` block, and continues to sleep using exponential backoff. If all 5 attempts fail this way, the system returns mock candles, presenting fake trading signals to the user.
- **Mitigation**: Use safe parsing block:
  ```python
  retry_after_raw = resp.headers.get("Retry-After", "1.0")
  try:
      retry_after = float(retry_after_raw)
  except ValueError:
      retry_after = 1.0 # Or parse date string
  ```

### 2. Assumption Stress-Testing: Event Loop Collision on Sequential Tasks
- **Assumption Challenged**: That `asyncio.create_task(run_scan_and_notify())` handles errors gracefully without leaking tasks.
- **Attack Scenario**: Telegram bot commands trigger many parallel `/scan_all` background tasks.
- **Blast Radius**: The background status checks using `_scan_status` prevent parallel executions of the underlying scanner, but multiple `run_scan_and_notify` coroutines will spawn, and all of them will return immediately with the same `_latest_scan_results` and spam the Telegram channel with duplicate reports.
- **Mitigation**: Control bot-level trigger rate limiting, or check `_scan_status == "running"` in `telegram_bot.py` and reply that a scan is already active.

---

## 🛡️ Verified Claims

1. **Rate Limiting 429 Retry-After Handling**:
   - *Claim*: Handles HTTP 429 by sleeping for the duration of the `Retry-After` header.
   - *Method*: Verified in code review (`analysis.py:316-322`) and unit test `test_fetch_candles_rate_limited` -> **PASS** (with robust error fallback caveat).
2. **Concurrency Limits (Semaphore)**:
   - *Claim*: Limits requests to 15 concurrent REST calls.
   - *Method*: Verified in code review (`analysis.py:410`, `545`) -> **PASS** (exchanges are sequential, but concurrent internally).
3. **Weex Adapter Integration**:
   - *Claim*: Correctly uses `get_active_symbols` to fetch and parse symbols ending in `_UMCBL`.
   - *Method*: Verified in code review of `weex_adapter.py:158` and integration in `analysis.py:551` -> **PASS**.
4. **HTML Escaping on Telegram Bot**:
   - *Claim*: Formatting strings sent to Telegram are escaped properly.
   - *Method*: Code review of `notifier.py` and Telegram bot commands -> **FAIL** (pre-built HTML tags are escaped and broken).
