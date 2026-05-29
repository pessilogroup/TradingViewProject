# Handoff Report — MTF Nested Insets Verification

## 1. Observation

- **Implementation File**: `nerves/workers/trading/capture_client.py`
  - Line 363-369: Resolves parent timeframe based on primary timeframe.
    ```python
    tf_lower = timeframe.lower()
    parent_timeframe = None
    if tf_lower in ("15m", "15"):
        parent_timeframe = "1H"
    elif tf_lower in ("1h", "60"):
        parent_timeframe = "4H"
    ```
  - Line 377-384: Concurrently gathers primary and parent timeframe data using `asyncio.gather` when `ohlcv_data` is not provided.
    ```python
    if parent_timeframe:
        # Concurrent fetching using asyncio.gather
        ohlcv_data, parent_ohlcv = await asyncio.gather(
            self._get_ohlcv_data(symbol, timeframe, candles_count),
            self._get_ohlcv_data(symbol, parent_timeframe, candles_count)
        )
    ```
  - Line 385-391: Catches exceptions at the parent block level:
    ```python
    except Exception as e:
        logger.error(f"Cannot perform local rendering: failed to retrieve OHLCV: {e}")
        return CaptureResult(
            success=False,
            error=f"OHLCV data retrieval failed: {e}",
            method=method
        )
    ```

- **Matplotlib Generator File**: `nerves/workers/trading/utils/chart_generator_mpl.py`
  - Line 21-22: Function signature has arguments `parent_timeframe: Optional[str] = None` and `parent_ohlcv: Optional[Union[List[List[Any]], List[Dict[str, Any]]]] = None`.
  - Static review confirms that `parent_timeframe` and `parent_ohlcv` are not referenced anywhere in the function body.

- **Adversarial Test Executions**:
  - Command: `pytest nerves/workers/trading/tests/unit/test_mtf_nested_adversarial.py`
  - Output: `4 passed in 5.12s`
  - Verbatim log from execution:
    ```
    nerves\workers\trading\tests\unit\test_mtf_nested_adversarial.py::test_parent_fetch_failure_causes_total_failure PASSED [ 25%]
    nerves\workers\trading\tests\unit\test_mtf_nested_adversarial.py::test_parent_fetch_timeout_slows_down_primary PASSED [ 50%]
    nerves\workers\trading\tests\unit\test_concurrency_load_mocked PASSED [ 75%]
    nerves\workers\trading\tests\unit\test_matplotlib_fallback_ignores_parent_data PASSED [100%]
    ```

## 2. Logic Chain

1. **Logical Step 1**: In `capture_client.py`, when `capture_screenshot` runs without pre-fetched `ohlcv_data`, the client fetches primary and parent data concurrently using `asyncio.gather`.
2. **Logical Step 2**: If either fetch fails, `asyncio.gather` raises the first exception. Because the entire fetch block is wrapped in a single `try...except`, any failure in parent timeframe data retrieval immediately aborts the screenshot attempt and returns `success=False`.
3. **Logical Step 3**: Therefore, a temporary network failure or API rate limit affecting only the parent timeframe's endpoint results in a total failure to generate any chart, instead of gracefully rendering the primary timeframe chart (verified in `test_parent_fetch_failure_causes_total_failure`).
4. **Logical Step 4**: In `chart_generator_mpl.py`, there is no layout drawing or secondary chart configuration matching the parent timeframe. Thus, during browser rendering failures where the system falls back to `mplfinance`, the output image lacks the inset chart (verified in `test_matplotlib_fallback_ignores_parent_data`).

## 3. Caveats

- **External Exchange APIs**: We mocked exchange API latency and failures during tests to maintain determinism. Live network conditions could vary.
- **Node.js Daemon Mode**: The investigation focused heavily on the Python capture client's local rendering modes (fallback paths) rather than the active Node.js daemon service, as local fallback is the critical resilience path.

## 4. Conclusion

The Multi-Timeframe (MTF) Nested Chart Inset layout implementation works reliably under normal conditions, but is vulnerable to **Primary-Parent Fetch Coupling** (where a failure to fetch parent data causes the entire primary chart generation to fail) and **Silent MTF Feature Loss** under Matplotlib fallback (where the inset is silently omitted).

## 5. Verification Method

To independently verify this:
1. Run the project tests using `pytest nerves/workers/trading/tests/unit/test_mtf_nested.py` to check standard functionality.
2. Run the adversarial tests using `pytest nerves/workers/trading/tests/unit/test_mtf_nested_adversarial.py` to confirm the behavior under fetch failures, slow parents, concurrent requests, and fallback scenarios.
