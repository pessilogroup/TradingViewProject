# Worker MTF 1 Task

Implement Multi-Timeframe (MTF) Nested Chart Inset Layouts in the Stealth Capture Studio.

## Mandatory Rules
- DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Requirements

### R1. Timeframe Mappings and Concurrent Data Fetching
- Locate the main capture pipeline in `nerves/workers/trading/main.py` and `nerves/workers/trading/capture_client.py` (or other relevant locations).
- Define mappings for nested timeframes: `15m` (parent `1H`) and `1H` (parent `4H`). Handle potential case variations (e.g., `15m`, `1h`, `1H`).
- When a nested timeframe is captured, fetch both target and parent timeframe candles concurrently using the exchange adapters and fallbacks. Make sure to use `asyncio.gather` for parallel fetching to minimize latency.
- Store parent timeframe candles in the payload / data structure passed to the HTML template under `parent_ohlcv` and parent timeframe name under `parent_timeframe`.

### R2. PiP Inset Chart Layout Rendering
- Modify the chart HTML rendering (`chart_template.html` located under `nerves/workers/trading/static/chart_template.html` or similar) to dynamically overlay a nested parent timeframe chart if parent candles are present in the payload.
- Create a container styled with glassmorphism to house this inset chart:
  - Background: `#1e222d` (or glassmorphism backdrop version of it)
  - Border radius: `8px`
  - Border: `rgba(255,255,255,0.08)`
  - Layout size and positioning should be clear and fit within the viewport (e.g. `1200x700`).
- Include a text label identifying the parent timeframe (e.g. "4H Parent Trend").
- Render an SVG arrow indicator (#2962ff) pointing from the inset chart to the main chart area.

### R3. Fallback Matplotlib Rendering
- Verify and ensure that if Playwright fails or is not used, the fallback Matplotlib rendering (`chart_generator_mpl.py`) succeeds as a single chart without exceptions. It does not need to show the nested parent chart, but it must not fail.

## Verification
- Run tests:
  - Run the build and run existing unit/integration tests to ensure no regressions.
  - Add or update tests verifying concurrent fetching of parent candles when querying `/api/vision/capture` for `1H` and `15m` timeframes, and single timeframe rendering for `4H`, `1D`, etc.
  - Verify that the Matplotlib fallback works cleanly.
- Report the specific test commands you ran and their results in your `handoff.md` file.
