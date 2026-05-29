# Changes Report

## Modified Files
- `nerves/workers/trading/tests/unit/test_mtf_nested_adversarial.py`
  - Updated `test_parent_fetch_failure_causes_total_failure` to align with the new resilient design of `PythonCaptureClient`.
  - Assert that when the parent timeframe fetching fails, the overall capture call succeeds (`res.success == True`).
  - Assert that the call to `generate_chart_lw` has `parent_timeframe=None` and `parent_ohlcv=None` (corresponding to `parent_candles=None`).

## Verification Results
- Executed unit tests in both test suites:
  - `test_mtf_nested.py` -> 7 passed in 7.28s.
  - `test_mtf_nested_adversarial.py` -> 4 passed in 4.59s.
