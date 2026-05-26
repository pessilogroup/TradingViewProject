# Plan - Automated "Scan All" Background Feature

## Objectives
Implement dynamic symbol discovery for active exchanges, execute unfiltered concurrent scanning with rate-limit protection, and expose `/api/scan/all` API endpoint and `/scan_all` Telegram bot command.

## Step-by-Step Execution Plan

### Step 1: Exploration and Feasibility Analysis
- **Goal**: Understand how Weex Adapter, Binance Adapter, and Bybit Adapter retrieve active linear contracts.
- **Details**:
  - Locate API endpoints for each exchange (e.g. Weex: `/api/v2/contract/public/symbols`, Bybit: `/v5/market/instruments-info`, Binance: `/fapi/v1/exchangeInfo`).
  - Analyze current scheduler configuration, API routing, and Telegram commands module.
- **Verification**: Explorer produces a clear report showing required changes.

### Step 2: Implement Dynamic Symbol Discovery
- **Goal**: Implement methods to fetch linear futures contract symbols dynamically from Weex, Binance, and Bybit.
- **Details**:
  - Add/update methods in adapters to fetch active futures symbols.
  - Implement a registry method or helper function to query all active exchanges for active linear contract list.
  - Ensure Weex filtering uses `_UMCBL` suffix.
- **Verification**: A unit test runs and returns list of symbols.

### Step 3: Implement Concurrency and Rate-Limit Protecting Scanner
- **Goal**: Scan 100+ active pairs concurrently without being rate-limited.
- **Details**:
  - Implement an async semaphore/queue to limit max concurrent requests.
  - Add retry-with-exponential-backoff logic for handling `HTTP 429` (Rate Limited) errors.
  - Integrate Trend Template and VCP scoring for each pair.
- **Verification**: Scanner can scan a simulated large list of symbols without blocking or failing on rate limit.

### Step 4: Expose API Endpoint `/api/scan/all`
- **Goal**: Expose an endpoint that triggers a full scan of all dynamic pairs.
- **Details**:
  - Add route `@app.get("/api/scan/all")` in `nerves/workers/trading/main.py` or separate router.
  - Make sure scan results are ranked (e.g., VCP detected first, then by Trend Template score descending).
- **Verification**: `GET /api/scan/all` returns valid JSON with ranked results.

### Step 5: Implement Telegram Command `/scan_all`
- **Goal**: Register and implement `/scan_all` Telegram command.
- **Details**:
  - Register `/scan_all` command in the Telegram bot.
  - Command executes the scan in a background task (so the bot doesn't time out or block).
  - Broadcast results to target chat ID(s) once complete (filtering for Trend Template score >= 6 or VCP detected).
- **Verification**: Mock bot execution or log output shows Telegram broadcast payload contains correct setups.

### Step 6: End-to-End Verification and Auditing
- **Goal**: Validate implementation correctness and run tests.
- **Details**:
  - Run the test suite.
  - Verify that Weex futures contract pairs compute VCP/Trend Template scores correctly.
  - Perform forensic integrity auditing.
- **Verification**: All tests pass. Auditor reports CLEAN.
