# Handoff Report: Adversarial Verification of MTF Nesting & Fallbacks

## 1. Observation

- **Project Path**: `c:\Users\pesil\working\mj_trading\TradingViewProject`
- **Adversarial Test File**: `nerves/workers/trading/tests/unit/test_mtf_nested_adversarial.py`
- **Unit Test File**: `nerves/workers/trading/tests/unit/test_mtf_nested.py`
- **Client Implementation File**: `nerves/workers/trading/capture_client.py`
- **Test Command Executed**:
  `python -m pytest nerves/workers/trading/tests/unit/test_mtf_nested.py nerves/workers/trading/tests/unit/test_mtf_nested_adversarial.py`
  - Output:
    ```
    nerves\workers\trading\tests\unit\test_mtf_nested.py::test_timeframe_mappings PASSED [  9%]
    nerves\workers\trading\tests\unit\test_mtf_nested.py::test_concurrent_fetching_nested PASSED [ 18%]
    nerves\workers\trading\tests\unit\test_mtf_nested.py::test_single_timeframe_no_parent PASSED [ 27%]
    nerves\workers\trading\tests\unit\test_mtf_nested.py::test_matplotlib_fallback_resilience PASSED [ 36%]
    nerves\workers\trading\tests\unit\test_mtf_nested.py::test_api_vision_capture_route PASSED [ 45%]
    nerves\workers\trading\tests\unit\test_mtf_nested.py::test_mtf_nested_resilience_on_parent_failure PASSED [ 54%]
    nerves\workers\trading\tests\unit\test_mtf_nested.py::test_mtf_nested_resilience_on_parent_failure_provided_ohlcv PASSED [ 63%]
    nerves\workers\trading\tests\unit\test_mtf_nested_adversarial.py::test_parent_fetch_failure_causes_total_failure PASSED [ 72%]
    nerves\workers\trading\tests\unit\test_mtf_nested_adversarial.py::test_parent_fetch_timeout_slows_down_primary PASSED [ 81%]
    nerves\workers\trading\tests\unit\test_mtf_nested_adversarial.py::test_concurrency_load_mocked PASSED [ 90%]
    nerves\workers\trading\tests\unit\test_mtf_nested_adversarial.py::test_matplotlib_fallback_ignores_parent_data PASSED [100%]
    ============================= 11 passed in 9.69s ==============================
    ```

- **Verification of `test_parent_fetch_failure_causes_total_failure` implementation**:
  - The test sets up a mock `_get_ohlcv_data` raising `RuntimeError("Parent fetch failed...")` for `tf == "4H"`.
  - It asserts `res.success` is `True`, and that the arguments passed to `generate_chart_lw` have `parent_ohlcv = None` and `parent_timeframe = None`.
  - However, there is no assertion verifying that the mock `_get_ohlcv_data` was actually called with `4H`.

- **Verification of `_local_capture` implementation in `capture_client.py`**:
  - Direct execution of `asyncio.gather` on line 379-383 has no timeout wrappers or handling for slow requests:
    ```python
    results = await asyncio.gather(
        self._get_ohlcv_data(symbol, timeframe, candles_count),
        self._get_ohlcv_data(symbol, parent_timeframe, candles_count),
        return_exceptions=True
    )
    ```

---

## 2. Logic Chain

1. **Mapping Bypass Risk**: In `test_parent_fetch_failure_causes_total_failure`, if the mapping logic fails to resolve `1h` to parent timeframe `4H`, the client skips calling `_get_ohlcv_data` for the parent timeframe entirely. Because the mock doesn't throw, and the test's assertions only verify that `parent_ohlcv` and `parent_timeframe` are `None` (which they would be if mapped to `None`), the test passes falsely. Therefore, this assertion is vulnerable to silent mapping breakages.
2. **Latency Blockage**: In `test_parent_fetch_timeout_slows_down_primary`, the test verifies that a slow parent fetch of 1.0s delays the total request by at least 1.0s (`assert elapsed >= 1.0`). In production, if the parent fetch hangs indefinitely or takes 10s, this will block the entire screenshot capture, risking gateway timeouts. There is currently no timeout guarding the parent fetch.
3. **Concurrency/Write Collision**: In `test_concurrency_load_mocked`, the client is mocked, bypassing actual Playwright rendering. In actual execution, concurrent requests without an explicit `save_path` default to `chart_lw_{symbol}_{timeframe}.png`, creating write contention/race conditions.

---

## 3. Caveats

- Playwright and CCXT are mocked in the unit/adversarial tests to allow running them in a sandboxed, network-restricted environment without requiring a browser or API keys.
- Live rendering issues (such as visual overlapping or HTML load failures) cannot be verified solely via mock unit assertions and require visual integration checks.

---

## 4. Conclusion

The updated adversarial test assertions are correct according to the current resilient implementation, but they suffer from **false pass vulnerability** (if mapping is broken) and do not protect against **high latency** (blocking on slow parent fetch) or **concurrency collisions** (multiple files writing to the same default path).

---

## 5. Verification Method

To verify these findings:
1. View the detailed challenge analysis in: `.agents/challenger_fixes_mtf_2/challenge.md`
2. Run the unit and adversarial test suites:
   `python -m pytest nerves/workers/trading/tests/unit/test_mtf_nested.py nerves/workers/trading/tests/unit/test_mtf_nested_adversarial.py`
3. To reproduce the false-pass vulnerability, temporarily modify `capture_client.py` to return `None` for parent timeframes, and observe that the adversarial test suite still passes without failures.
