## 2026-05-27T06:07:02Z
Analyze the capture engine and related HTML/Matplotlib template structures in order to design the MTF Nested Chart Inset Layouts.
1. Locate `/api/vision/capture` endpoint in `nerves/workers/trading/main.py`.
2. Analyze how it fetches candles (which exchange adapters are called, how fallbacks are managed).
3. Find where the template rendering (`chart_template.html`) is invoked and what data context is passed to it.
4. Locate the Matplotlib fallback rendering mechanism and identify how it works when Playwright fails.
5. Generate a detailed design report outlining the changes needed for:
   - Defining the timeframe mapping.
   - Concurrent parent/child candle fetching.
   - Injecting parent candles/timeframes to HTML payload.
   - Designing the HTML/CSS glassmorphism overlay and SVG arrow in `chart_template.html`.
   - Ensuring Matplotlib fallback renders a clean single chart.

Write your report to c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\explorer_mtf_1\analysis.md and notify me.
