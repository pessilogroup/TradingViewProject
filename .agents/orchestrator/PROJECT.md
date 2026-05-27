# Project: Multi-Timeframe (MTF) Nested Chart Inset Layouts

## Architecture
- Nested timeframe mappings: `15m` maps to parent `1H`, and `1H` maps to parent `4H`.
- Concurrent data fetching using FastAPI and async adapters to retrieve both target timeframe and parent timeframe candle data.
- Frontend rendering in HTML template (`chart_template.html`) which detects the presence of parent candles and overlays a nested PiP inset chart.
- Styling: Modern glassmorphism floating container with background `#1e222d`, border-radius `8px`, and border `rgba(255,255,255,0.08)`.
- Directional arrow indicator: SVG arrow (`#2962ff`) pointing from the inset chart to the main chart area.
- Robust fallback: Fallback matplotlib rendering that operates correctly (as a single chart without exceptions) if Playwright browser rendering fails.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Exploration & Architecture | Identify how data is fetched in `/api/vision/capture` and where fallback matplotlib rendering is implemented. | None | PLANNED |
| 2 | Concurrent Fetching & Payload | Define mappings and fetch parent + child candles concurrently, updating the payload. | M1 | PLANNED |
| 3 | HTML PiP Inset Rendering | Modify `chart_template.html` to render nested inset chart, glassmorphism container, and SVG arrow. | M2 | PLANNED |
| 4 | Matplotlib Fallback | Ensure matplotlib fallback rendering succeeds as a single chart if Playwright is absent/fails. | M3 | PLANNED |
| 5 | E2E Testing & Audit | Create and run tests for nested rendering, single timeframe rendering, and fallback. Perform Forensic Audit. | M4 | PLANNED |

## Interface Contracts
### /api/vision/capture
- Input query params: `symbol`, `timeframe`.
- Payload passed to the HTML template includes:
  - `candles`: target candles
  - `parent_candles`: parent candles (if nested)
  - `parent_timeframe`: string representation of parent timeframe (if nested)
