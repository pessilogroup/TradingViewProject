# Project: TradingView Edge Node Ecosystem Evaluation

## Architecture
- **FastAPI Webhook Node**: `nerves/workers/trading/gateway/webhook.py` handles TV indicator alerts, performing auth validation, IP whitelisting, rate-limiting, and schema validation.
- **Signal Processor & Circuit Breakers**: `nerves/workers/trading/processor/signal_processor.py` validates timeframes. Live trades only allow 1H signals (60, 1h, 60m). All non-1H signals are isolated/rejected by the circuit breaker.
- **TradingView CDP connection**: Port 9222. Connects to TradingView desktop app via Chrome DevTools Protocol to fetch version JSON and query indicator alerts/charts.
- **Telegram Bot service**: `nerves/workers/trading/telegram_bot.py`. Handles alert notifications and interactive trade approvals. Must return correctly structured message coordinates `List[Tuple[int, int]]` (SCAR-G2-001).

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Exploration & Diagnostics | Find existing test coverage, review codebase hooks, check CDP capability, and verify Telegram bot structure | None | DONE |
| 2 | Webhook Stability & Circuit Breaker Verification | Validate webhook concurrency, auth gate, 15 req/min rate limit (HTTP 429), and 1H circuit breaker isolation | M1 | DONE |
| 3 | CDP & Telegram Hub Verification | Verify CDP JSON output on port 9222, verify Telegram bot return type compliance (SCAR-G2-001), check signal mapping | M2 | DONE |
| 4 | Verification & Forensic Audit | Run Reviewers and Forensic Auditor to ensure clean verdict, check against SCAR codes | M3 | DONE |

## Interface & Safety Contracts
- **Webhook Rate Limiting**: 15 requests per minute per IP. Hits HTTP 429 "Too Many Requests".
- **Timeframe Circuit Breaker**: Only accepts intervals `60`, `1h`, or `60m`. Rejects `4h`, `15m`, `D`, etc.
- **Telegram Approval Return Type**: `send_interactive_trade_approval` must return `List[Tuple[chat_id, message_id]]`. Under no circumstances should it return a `bool`.
- **CDP Debug Connection**: Querying `http://localhost:9222/json/version` must return a valid JSON object matching the Chromium version info schema.
