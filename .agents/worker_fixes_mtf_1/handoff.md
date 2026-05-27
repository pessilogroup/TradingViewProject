# Handoff Report — MTF Nested Chart Inset Layouts Resilience

## 1. Observation
In `nerves/workers/trading/capture_client.py` (lines 377-383):
```python
                if parent_timeframe:
                    # Concurrent fetching using asyncio.gather
                    ohlcv_data, parent_ohlcv = await asyncio.gather(
                        self._get_ohlcv_data(symbol, timeframe, candles_count),
                        self._get_ohlcv_data(symbol, parent_timeframe, candles_count)
                    )
```
Any exception raised by `self._get_ohlcv_data(symbol, parent_timeframe, candles_count)` propagated directly out, failing the entire `asyncio.gather` and causing the capture to fail.

Similarly, in lines 393-398:
```python
            if parent_timeframe:
                try:
                    candles_count = config.CHART_CANDLES_COUNT
                    parent_ohlcv = await self._get_ohlcv_data(symbol, parent_timeframe, candles_count)
                except Exception as e:
                    logger.warning(f"Failed to retrieve parent OHLCV data: {e}")
```
Although it caught the exception, it didn't reset `parent_timeframe = None`, which meant subsequent rendering still passed `parent_timeframe` down.

## 2. Logic Chain
- To prevent parent timeframe candle fetching failures from blocking the primary chart render, we must catch exceptions on the parent timeframe fetch task within `asyncio.gather`.
- We achieve this by using `return_exceptions=True` in `asyncio.gather`.
- We check the result of the first task (primary timeframe). If it's an exception, we raise it because rendering the main chart requires the primary data.
- We check the result of the second task (parent timeframe). If it's an exception, we log a warning and set `parent_ohlcv = None` and `parent_timeframe = None`. This disables the nested inset container layout in the HTML template (lines 294-296 of `chart_template.html`: `if (chartData.parent_ohlcv && chartData.parent_ohlcv.length > 0)`).
- This allows rendering of the primary chart to succeed as a single chart without nested insets.

## 3. Caveats
- Playwright-based lightweight-charts local rendering tests require the Playwright Chromium browser to be available. Matplotlib-based rendering acts as a fallback if lightweight-charts fails.

## 4. Conclusion
The implementation successfully catches concurrent fetch errors for parent timeframe candles, logging a warning and falling back to rendering the primary chart as a single chart without nested insets.

## 5. Verification Method
Verify the fixes by running the unit tests:
```powershell
pytest nerves/workers/trading/tests/unit/test_mtf_nested.py
```
Expected output: 7 passed.
Also run:
```powershell
pytest nerves/workers/trading/tests/unit/test_capture_client_routing.py
pytest nerves/workers/trading/tests/unit/test_chart_generators.py
```
Expected output: all passed.
Files to inspect:
- `nerves/workers/trading/capture_client.py` (lines 373-401)
- `nerves/workers/trading/tests/unit/test_mtf_nested.py` (added unit tests at the end)
