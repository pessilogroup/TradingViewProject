# Project: Automated "Scan All" Background Feature

## Architecture
- Dynamic symbol retrieval from Weex, Binance, Bybit adapters using exchange-specific endpoints.
- Unfiltered, rate-limit protected concurrent scanning of 100+ pairs.
- FastAPI endpoint `/api/scan/all` exposing results ranked by VCP detection and Trend Template score.
- Telegram Command `/scan_all` triggering background scanning and broadcasting top setups.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Exploration & Architecture | Explore symbol retrieval APIs, scanner concurrency models, and Telegram bot handlers. | None | DONE |
| 2 | Dynamic Symbol Discovery | Implement dynamic linear symbol listing for Weex, Binance, Bybit in exchange adapters and registry. | M1 | PLANNED |
| 3 | Concurrency & Rate-limiting | Implement concurrent scanning logic with exponential back-off and queue management. | M2 | PLANNED |
| 4 | FastAPI Endpoint | Implement GET /api/scan/all route returning ranked VCP and Trend Template scores. | M3 | PLANNED |
| 5 | Telegram Command | Implement /scan_all command to trigger scanning in background and broadcast results. | M4 | PLANNED |
| 6 | Testing & Audit | Add integration tests, run full test suite, perform Forensic Auditing. | M5 | PLANNED |

## Interface Contracts
### ExchangeAdapter ↔ Scanner
- `async get_active_symbols() -> List[str]`: New interface method to list active linear futures contracts.
- Weex adapter must return symbols ending in `_UMCBL`.
- Binance adapter must return active USDT-M contracts.
- Bybit adapter must return active USDT linear contracts.
