# Handoff Report: Scan All Background Feature Review

## 1. Observation

- **Reviewed Files**:
  - `nerves/workers/trading/analysis.py` (REST scanner, rate limiting, concurrency, Weex adapter integration)
  - `nerves/workers/trading/main.py` (FastAPI endpoints and background task invocation)
  - `nerves/workers/trading/telegram_bot.py` (`cmd_scan_all`, `cmd_scan_enhanced`, status and formatting)
  - `nerves/workers/trading/notifier.py` (HTML escaping logic via `sanitize_for_telegram_html`)

- **Integrity Violation (Mock Candles Facade)**:
  - In `nerves/workers/trading/analysis.py` lines 397-398:
    ```python
    logger.error(f"Failed to fetch candles for {symbol} on {exchange_name} after {max_retries} attempts.")
    return generate_mock_candles(limit)
    ```
    This function `generate_mock_candles` returns a list of 365 fake candles with static prices (close = 100.5) and volume (1000.0) to simulate successful data fetching.

- **HTML-Escaping Formatting Bug**:
  - In `nerves/workers/trading/notifier.py` line 17, `sanitize_for_telegram_html` replaces `<` and `>`:
    ```python
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    ```
  - In `nerves/workers/trading/telegram_bot.py` lines 815-816 and 886-887, commands formatting HTML strings call this:
    ```python
    from notifier import sanitize_for_telegram_html
    text = sanitize_for_telegram_html("\n".join(lines))
    ```
    These strings pre-build HTML tags such as `<b>Scan Results</b>`, `<pre>`, `</pre>`, and `<code>{s}</code>`.

- **Concurrency and Exchange Scanning**:
  - In `nerves/workers/trading/analysis.py` lines 547-582, the scan loops sequentially across exchanges:
    ```python
    for eid in exchange_ids:
        ...
        if tasks:
            exchange_results = await asyncio.gather(*tasks)
            results.extend(exchange_results)
    ```
  - The concurrency semaphore is set to 15: `semaphore = asyncio.Semaphore(15)`.

- **Verification Commands & Output**:
  - Command: `python -m pytest tests/unit/test_scan_all.py` inside `nerves/workers/trading`
  - Output: `============================== 9 passed in 4.49s ==============================`
  - Command: `python -m ruff check nerves/workers/trading/analysis.py nerves/workers/trading/main.py nerves/workers/trading/telegram_bot.py`
  - Output: Found 21 errors (including unused variables, unused imports, extraneous f-strings, and imports not at top of file).

---

## 2. Logic Chain

- **Step 1**: The unit test execution results prove that the logic executes successfully in isolated mock conditions, and the basic HTTP endpoints respond properly (Observation 1).
- **Step 2**: However, if a real symbol data fetch fails or is severely rate-limited (429) across all 5 retries, the code in `analysis.py` reverts to the mock candle generator (Observation 1). This hides connection/network/rate failures and feeds 365 fake candles into the Trend Template and VCP detectors. This constitutes an **Integrity Violation** since a facade implementation is used to fake a successful result.
- **Step 3**: In `notifier.py`, `sanitize_for_telegram_html` is written to escape raw HTML characters (`<` and `>`) to prevent Telegram parse errors (Observation 1). However, the Telegram bot commands like `cmd_scan_all` and `cmd_scan_enhanced` build their formatted output using HTML strings and *then* pass the entire block to `sanitize_for_telegram_html` (Observation 1). Consequently, all formatting tags (`<b>`, `<pre>`, `<code>`) are escaped into `&lt;b&gt;`, `&lt;pre&gt;`, `&lt;code&gt;`. When Telegram receives the message, it displays the literal text codes rather than rendering formatted text, breaking the user interface.
- **Step 4**: The semaphore correctly limits concurrent HTTP sessions to 15 within an exchange. However, since the exchange list is processed sequentially via a `for eid in exchange_ids` loop, the scan blocks on a per-exchange basis (Observation 1). This creates a performance bottleneck when multiple exchanges are scanned.
- **Step 5**: Ruff check output indicates there are 21 style, syntax, and formatting errors that violate standard code formatting and import guidelines (Observation 1).

---

## 3. Caveats

- We did not perform interactive testing of the Telegram Bot using a live Bot Token since it requires external network access and configuration. The escaping behavior was verified by reviewing the code logic of `sanitize_for_telegram_html` and tracking how it handles input from `cmd_scan_all` and other commands.
- We did not modify the source code to fix the issues, as this agent is review-only.

---

## 4. Conclusion

- **Verdict**: **REQUEST_CHANGES**
- **Critical Issues**:
  1. **INTEGRITY VIOLATION**: The fallback to `generate_mock_candles` on data fetch failure is a facade that masks real API or network failures, generating mock metrics instead of reporting an error.
  2. **Telegram HTML Escaping**: Pre-built HTML tags in bot commands are escaped, breaking Telegram UI formatting.
  3. **Ruff Style Compliance**: 21 formatting and syntax errors must be resolved.
- **Actionable Work**:
  - Replace the mock candle fallback with an exception propagation or empty-list return that cleanly records a "Failed to fetch data" status on the `ScanResult`.
  - Fix Telegram bot formatting by avoiding `sanitize_for_telegram_html` on pre-formatted HTML text blocks, or rewrite formatting to use markdown blocks that the sanitizer converts safely.
  - Fix the 21 linting issues surfaced by Ruff.

---

## 5. Verification Method

- **Command to Run**:
  Run pytest within `nerves/workers/trading` to verify basic logic:
  ```powershell
  python -m pytest tests/unit/test_scan_all.py
  ```
  Run Ruff check to verify style correctness:
  ```powershell
  python -m ruff check nerves/workers/trading/analysis.py nerves/workers/trading/main.py nerves/workers/trading/telegram_bot.py
  ```
- **Files to Inspect**:
  - `nerves/workers/trading/analysis.py` (check if `generate_mock_candles` fallback has been removed from retry blocks).
  - `nerves/workers/trading/telegram_bot.py` (check if HTML commands format without breaking).
  - `.agents/reviewer_1/review.md` (detailed review findings).
- **Invalidation Conditions**:
  - If any of the 9 unit tests fail.
  - If Ruff check returns formatting or style errors.
  - If Telegram formatting continues to display escaped raw HTML tags (`&lt;b&gt;` etc.).
