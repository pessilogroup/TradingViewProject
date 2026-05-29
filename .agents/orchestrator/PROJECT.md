# Project: TradingView Desktop CDP and Webhook Automation

## Architecture
- **TradingView Desktop**: Runs on Windows with `--remote-debugging-port=9222`. Installed either in standard directories or as an MSIX package.
- **CDP client**: Python script using standard libraries or light-weight CDP protocol (or wrapping node.js MCP CLI) to connect to port 9222.
- **FastAPI Webhook Server**: Ingress point (`/webhook`) that parses indicator signal payloads and stores them in the database (`indicator_signals` table in `trades.db`).

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1_Explorer | Analyze CDP target, standard/MSIX paths, DOM selectors, webhook payload | none | DONE |
| 2 | M2_Implementer | Implement auto-launcher, CDP symbol/indicator extractor, and E2E webhook poster | M1 | IN_PROGRESS |
| 3 | M3_Verification | Verify E2E run against live server and SQLite DB, perform forensic audit | M2 | PLANNED |

## Interface Contracts
- **CDP Server**: `http://localhost:9222/json/version`
- **FastAPI /webhook**:
  - Request body (JSON indicator signal payload, e.g. symbol, interval, close, studies like ATR14, SMA50, SMA150, SMA200).
  - Query parameter: `?secret=<WEBHOOK_SECRET>` or header token for validation.
  - Return: HTTP 200/202 with confirmation.
