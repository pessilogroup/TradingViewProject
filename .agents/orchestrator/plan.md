# Plan - CDP & Webhook Integration

## Mission
Automate connecting to TradingView Desktop via Chrome DevTools Protocol (CDP) on port 9222 (including auto-launching and MSIX packaging path resolution), extracting live study values and dynamic active symbols from the active chart page, and validating the integration by sending simulated real data payloads to the webhook ingress.

## Milestones

### Milestone 1: Explorer Phase (Analysis & Extraction Research)
- Task: Analyze the existing `tradingview-mcp` code, standard/MSIX paths of TradingView Desktop on Windows, HTML/DOM structure of TradingView Desktop for symbol and study values, and `/webhook` ingress payload constraints.
- Done when: Handoff file created detailing paths, selectors, and payload schema.

### Milestone 2: Implementation Phase (Script Development)
- Task: Create/extend a script (e.g. `nerves/workers/trading/scripts/tv_cdp_webhook.py`) that:
  1. Auto-launches TradingView Desktop (handling standard paths and MSIX via `Get-AppxPackage`) with `--remote-debugging-port=9222`.
  2. Establishes CDP connection to port 9222 and parses the active symbol.
  3. Extracts latest close price, timeframe interval, and study indicators (SMA50, SMA150, SMA200, ATR14) from the chart.
  4. Assembles the webhook payload, POSTs it to the `/webhook` ingress, and verifies HTTP 200.
- Done when: Implementation passes basic manual tests and code is clean.

### Milestone 3: Verification & Auditing Phase (Test Suite & Verification)
- Task: Add integration test/automated verification to run the script and check database persistence. Run the Forensic Auditor.
- Done when: All tests pass, E2E validation succeeds, and Forensic Auditor reports clean.
