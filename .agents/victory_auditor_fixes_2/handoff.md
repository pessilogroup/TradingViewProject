# Forensic Audit Report & Handoff

**Work Product**: "Scan All" background scanning feature code changes and tests
**Profile**: General Project (Development Mode / Demo Mode / Benchmark Mode compliant)
**Verdict**: CLEAN

### Phase Results
- **Hardcoded output detection**: PASS — Scanned `nerves/workers/trading/analysis.py` and the unit test files. All metrics (SMA, ATR, RS, Trend Template score, VCP) are calculated dynamically from input OHLCV lists. There are no hardcoded responses, pre-computed tables, or shortcuts to satisfy test assertions.
- **Facade detection**: PASS — The implementation in `analysis.py` contains genuine calculations. For example, ATR14 computes true range across a sliding window, SMA calculations use trailing list sums, and the RS ratio computes real relative performance versus BTC candles.
- **Pre-populated artifact detection**: PASS — Evaluated directory structure for fake test results, logs, or reports created prior to execution. All logs are dynamically generated at run-time.
- **Build and run**: PASS — The test suite was successfully executed using `python -m pytest` and all 12 tests passed successfully.
- **Output verification**: PASS — Formulas for indicators were verified to be authentic:
  - SMA: `sma50 = sum(prices[-50:]) / 50`
  - ATR14: `tr = max(h - low_val, abs(h - prev_c), abs(low_val - prev_c))`
  - RS ratio vs BTC: Compare symbol's 50-period return ratio against BTC's 50-period return ratio.
  - VCP: Volume contraction (`volume_ratio < 0.5`) and range contraction (`range_ratio < 0.5`).
- **Dependency audit**: PASS — No forbidden code reuse, execution delegation, or wrappers of external libraries are used for core logic. All scan metrics and rate limit handlers are implemented directly in Python.

---

## 1. Observation

- **Implementation Location**:
  - `nerves/workers/trading/analysis.py`: Lines 277-394 (`fetch_candles_with_retry` fetching from Bybit, WEEX, and Binance REST endpoints with 429 backoff), lines 396-505 (`_calculate_scan_result` executing SMA, ATR, RS, and VCP calculations), and lines 617-697 (`scan_all_configured_exchanges` managing bulk concurrent scan with lock).
- **Test File Locations**:
  - `nerves/workers/trading/tests/unit/test_scan_all.py`
  - `nerves/workers/trading/tests/unit/test_rate_limit_simulation.py`
  - `nerves/workers/trading/tests/unit/test_scan_all_stress.py`
- **Execution Output**:
  - Run Command: `python -m pytest nerves/workers/trading/tests/unit/test_scan_all.py nerves/workers/trading/tests/unit/test_rate_limit_simulation.py nerves/workers/trading/tests/unit/test_scan_all_stress.py`
  - Verbatim Result:
    ```
    nerves\workers\trading\tests\unit\test_scan_all.py::test_fetch_candles_weex_success PASSED
    nerves\workers\trading\tests\unit\test_scan_all.py::test_fetch_candles_bybit_success PASSED
    nerves\workers\trading\tests\unit\test_scan_all.py::test_fetch_candles_binance_success PASSED
    nerves\workers\trading\tests\unit\test_scan_all.py::test_fetch_candles_rate_limited PASSED
    nerves\workers\trading\tests\unit\test_scan_all.py::test_fetch_candles_failure_fallback PASSED
    nerves\workers\trading\tests\unit\test_scan_all.py::test_scan_single_symbol_rest PASSED
    nerves\workers\trading\tests\unit\test_scan_all.py::test_scan_all_configured_exchanges PASSED
    nerves\workers\trading\tests\unit\test_scan_all.py::test_api_scan_all_endpoint PASSED
    nerves\workers\trading\tests\unit\test_scan_all.py::test_telegram_cmd_scan_all PASSED
    nerves\workers\trading\tests\unit\test_rate_limit_simulation.py::test_rate_limit_robustness_simulation PASSED
    nerves\workers\trading\tests\unit\test_scan_all_stress.py::test_scan_all_concurrency_and_stress PASSED
    nerves\workers\trading\tests\unit\test_scan_all_stress.py::test_scan_all_endpoint_stress PASSED
    ============================= 12 passed in 4.89s ==============================
    ```

## 2. Logic Chain

1. **Calculations Veracity**: Inspecting `_calculate_scan_result` shows that indicators are computed on-the-fly from standard OHLCV prices (`ohlcv = await fetch_candles_with_retry(...)`). No hardcoded results exist in source code.
2. **Test Authenticity**:
   - `test_rate_limit_simulation.py` patches `asyncio.sleep` with a virtual clock tracking function and mocks 429 API rate limits. It asserts `total_429s == 200` and validates that the task's execution elapsed time is `>= 9.875s`, which proves that exponential backoff rules (1.5x factor over retries) were executed realistically.
   - `test_scan_all_stress.py` executes a concurrent run on 200 mock symbols. It checks that concurrent requests never exceed the Semaphore limit (`max_active_requests <= 15`) and tracks memory allocation difference using `psutil` and `gc` to verify that memory growth is less than 10.0 MB (`assert growth < 10.0`).
3. **Execution Success**: The 12 unit tests pass completely.
4. **Verdict**: Because there are no integrity violations (no facades, no hardcoding, no pre-populated artifacts) and the tests themselves are structurally robust and verify actual runtime logic, the work product is rated **CLEAN**.

## 3. Caveats

- The memory leak test is reliant on the availability of `psutil`. If `psutil` is missing from the running environment, memory usage checks are skipped, but the assertions on execution correctness, concurrency count, and endpoint behavior still execute.

## 4. Conclusion

The "Scan All" background feature is cleanly and authentically implemented. Calculations are based on dynamic inputs from registered exchange adapters, and the tests verify rate-limiting backoff and concurrent stress/concurrency safety bounds realistically.

## 5. Verification Method

To verify the audit findings independently:
1. Run the test suite:
   ```powershell
   python -m pytest nerves/workers/trading/tests/unit/test_scan_all.py nerves/workers/trading/tests/unit/test_rate_limit_simulation.py nerves/workers/trading/tests/unit/test_scan_all_stress.py
   ```
2. Verify that all 12 tests compile and pass.
3. Inspect `nerves/workers/trading/analysis.py` lines 396-505 to verify that `_calculate_scan_result` does not contain hardcoded return values.
