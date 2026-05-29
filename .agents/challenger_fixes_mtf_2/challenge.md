# Challenge Report: Adversarial Verification of MTF Nesting & Fallbacks

## Challenge Summary

**Overall risk assessment**: MEDIUM

While the unit and adversarial test suites run and pass successfully, the adversarial test suite has structural vulnerabilities that could lead to false passes or fail to catch critical production failure modes (such as resource starvation or high latency under network degradation).

---

## Challenges

### [High] Challenge 1: False Pass Vulnerability in Parent Fetch Failure Test

- **Assumption challenged**: The test `test_parent_fetch_failure_causes_total_failure` assumes that a passing test guarantees the client gracefully handles a failed parent fetch while correctly identifying the parent timeframe.
- **Attack scenario**: If the timeframe mapping logic in `_local_capture` is broken or changed such that `"1h"` maps to `None` (no parent timeframe), the client will skip fetching the parent timeframe entirely. The mocked `_get_ohlcv_data` will not be called for the parent, and no exception will be raised. The client will call `generate_chart_lw` with `parent_timeframe=None` and `parent_ohlcv=None`. The test assertions will verify that `res.success` is `True` and the parent parameters are `None` — and the test will **pass falsely**, failing to detect that the parent mapping/fetching logic is broken.
- **Blast radius**: Broken timeframe mapping or parent fetching logic could be deployed to production, causing parent insets to silently disappear from charts without triggering test failures.
- **Mitigation**: Assert that `_get_ohlcv_data` was actually invoked with the parent timeframe parameter (`"4H"`). This guarantees that parent fetch was attempted and failed, rather than bypassed.
  ```python
  # Add assertion in test_parent_fetch_failure_causes_total_failure:
  called_tfs = [call[0][1] for call in client._get_ohlcv_data.call_args_list]
  assert "4H" in called_tfs
  ```

---

### [Medium] Challenge 2: Lack of Timeout / Latency SLA on Parent Timeframe Fetching

- **Assumption challenged**: The test `test_parent_fetch_timeout_slows_down_primary` assumes it is acceptable for a slow parent timeframe fetch to block and delay the primary chart rendering indefinitely.
- **Attack scenario**: The current implementation of `_local_capture` gathers the primary and parent timeframe fetches using `asyncio.gather` without any timeout wrapping the parent fetch. If the exchange API or CCXT call for the parent timeframe hangs or takes 5+ seconds due to rate limits or network issues, the entire screenshot request is blocked.
- **Blast radius**: API Gateway timeouts (typically 5-10s) and severe degradation of real-time alert routing speed.
- **Mitigation**: Wrap the parent timeframe fetch task in an `asyncio.wait_for(..., timeout=0.5)` block. If a timeout occurs, treat it identically to a fetch failure (log a warning, set parent parameters to `None`, and proceed with rendering the primary chart). Update the adversarial test to simulate a 5.0-second delay for the parent timeframe, and assert that the overall request completes in `< 0.6` seconds and succeeds.

---

### [Medium] Challenge 3: Inadequate Concurrency Mocking

- **Assumption challenged**: `test_concurrency_load_mocked` assumes that concurrent execution of `capture_screenshot` is safe because the mocked test passes.
- **Attack scenario**: The test mocks out `generate_chart_lw` (Playwright) and `_get_ohlcv_data`. In reality, launching multiple concurrent Playwright headless chromium instances creates a huge spikes in CPU/memory usage and can crash the worker process. Additionally, if multiple requests do not specify a `save_path`, they default to the same filename `chart_lw_{symbol}_{timeframe}.png`, leading to file write locks/race conditions.
- **Blast radius**: Worker node crash due to OOM, or corrupted chart screenshots sent to clients.
- **Mitigation**: Add a semaphore constraint in the worker/client (e.g. `asyncio.Semaphore(3)`) to limit concurrent Playwright rendering tasks, and ensure that the test validates concurrency limits or dynamic unique filenames are generated when no path is provided.

---

## Stress Test Results

| Scenario | Expected Behavior | Actual/Predicted Behavior | Pass/Fail |
|---|---|---|---|
| Timeframe mapping broken (returns `None` for `"1h"`) | Test `test_parent_fetch_failure_causes_total_failure` should fail | Test passes falsely (no check that `"4H"` fetch was attempted) | **FAIL** |
| Parent fetch takes 5.0 seconds | Request completes within 0.5s by dropping parent data | Request is blocked for 5.0s, delaying the primary chart | **FAIL** |
| Concurrent requests without `save_path` | Dynamic unique filenames generated or safe execution | Overwrite each other or cause file write locks | **FAIL** |

---

## Unchallenged Areas

- **Playwright actual browser rendering**: Mocked out to keep tests lightweight and independent of system GUI/browser availability.
- **CCXT integration**: Mocked out since actual exchange connection requires credentials and external network access, which is blocked under `CODE_ONLY` network mode.
