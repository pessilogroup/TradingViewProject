# Plan - Multi-Timeframe (MTF) Nested Chart Inset Layouts

## Objectives
Implement concurrent fetching of nested parent timeframes (`15m` -> `1H`, `1H` -> `4H`) in the capture pipeline, support PiP inset layouts in `chart_template.html` with glassmorphism styling and directional arrows, and ensure robust single-chart Matplotlib fallback rendering.

## Step-by-Step Execution Plan

### Step 1: Exploration
- **Goal**: Understand current candle fetching, template context construction, rendering logic, and Matplotlib fallback in `main.py` and `chart_template.html`.
- **Worker**: Explorer subagent.
- **Verification**: Handoff containing relevant code locations and planned structure.

### Step 2: Implement Concurrent Fetching and Payload Structure
- **Goal**: Implement mappings for nested timeframes and concurrent fetching of both target and parent candles (if mapped).
- **Details**:
  - Define `NESTED_TIMEFRAMES = {"15m": "1H", "1H": "4H"}`.
  - Concurrently fetch candles for both timeframe and parent timeframe using `asyncio.gather`.
  - Pass `parent_candles` and `parent_timeframe` to the HTML rendering payload.
- **Worker**: Worker subagent.
- **Verification**: Unit tests proving that calling the capture flow for `1H` concurrently requests both `1H` and `4H` data.

### Step 3: Implement HTML PiP Inset Rendering
- **Goal**: Update `chart_template.html` to render the inset chart using Lightweight Charts (or the library in use) when `parent_candles` are present.
- **Details**:
  - Add nested container with glassmorphism styling (`#1e222d` background, `8px` border radius, `rgba(255,255,255,0.08)` border).
  - Label indicating the parent timeframe.
  - SVG arrow indicator pointing from inset chart to main chart area (color `#2962ff`).
- **Worker**: Worker subagent.
- **Verification**: Verify inset chart displays correctly in rendered image.

### Step 4: Ensure Matplotlib Fallback
- **Goal**: Re-verify that Matplotlib fallback renders a single chart without nested insets or exceptions if Playwright fails.
- **Details**:
  - Verify that the Matplotlib fallback logic does not break when `parent_candles` are present. It should simply ignore them and draw a single chart.
- **Worker**: Worker subagent.
- **Verification**: Integration smoke test running without Playwright.

### Step 5: Testing and Forensic Auditing
- **Goal**: Verify robustness, functionality, and clean audit verdict.
- **Worker**: Reviewers, Challenger, Forensic Auditor.
- **Verification**: Successful test runs and CLEAN audit verdict.
