## 2026-05-26T16:53:49Z
**Context**: We need to make critical code improvements to the "Scan All" background feature based on reviewer feedback.
**Role**: Feature Implementer & QA
**TypeName**: teamwork_preview_worker
**Workspace**: inherit
**Task**:
1. Modify `nerves/workers/trading/analysis.py`:
   - In `fetch_candles_with_retry`, remove the mock candle fallback: do NOT call `generate_mock_candles(limit)` on failure. Instead, raise a `RuntimeError(f"Failed to fetch candles for {symbol} on {exchange_name} after {max_retries} attempts.")`.
   - In `scan_all_configured_exchanges()`, flatten all symbol scanning tasks across all exchanges and execute them concurrently to prevent sequential exchange-level bottlenecks. First retrieve active symbols and BTC benchmark info for all exchanges concurrently using `asyncio.gather`, then create a single flat list of `scan_single_symbol_rest` tasks, and run them concurrently using `asyncio.gather(*tasks)` sharing the 15-semaphore concurrency limit. Ensure error handling at exchange symbol/benchmark fetch is preserved (log warning on failure, do not abort scan).
2. Modify `nerves/workers/trading/telegram_bot.py`:
   - Define a module-level `running_tasks = set()` to store strong references of running background tasks.
   - In `cmd_scan_all`, store a strong reference to the background task to prevent garbage collection:
     ```python
     task = asyncio.create_task(run_scan_and_notify())
     running_tasks.add(task)
     task.add_done_callback(running_tasks.discard)
     ```
   - Fix Telegram HTML escaping by converting `cmd_scan_all` and `cmd_scan_enhanced` to format their text using Markdown syntax (e.g. `**text**` for bold, ` ``` ` for preformatted blocks, `` ` `` for code blocks/symbols) and then call `sanitize_for_telegram_html` on the combined message text before passing it to Telegram.
3. Modify `nerves/workers/trading/tests/unit/test_scan_all.py`:
   - Update the unit test `test_fetch_candles_failure_fallback` so that it expects a `RuntimeError` on failure instead of checking for mock candles.
4. Run style formatting and syntax checks:
   - Run `python -m ruff check nerves/workers/trading/analysis.py nerves/workers/trading/main.py nerves/workers/trading/telegram_bot.py --fix` to autofix lint errors.
   - Manually fix any remaining Ruff violations (such as unused variables, unused imports, extraneous f-strings, E722 bare excepts, ambiguous `l` variables, and module-level imports not at top) in these files.
5. Verify tests:
   - Run the full test suite using `python -m pytest nerves/workers/trading/tests/unit/test_scan_all.py nerves/workers/trading/tests/unit/test_rate_limit_simulation.py nerves/workers/trading/tests/unit/test_scan_all_stress.py` to ensure all tests pass cleanly.
6. Write a detailed handoff report in c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\worker_fixes_1\handoff.md listing the changes made and build/test verification results.
