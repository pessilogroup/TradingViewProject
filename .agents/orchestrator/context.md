# Context & Requirements Index

## Workspace
- Root: `c:/Users/pesil/working/mj_trading/TradingViewProject`
- Working Directory: `c:/Users/pesil/working/mj_trading/TradingViewProject/.agents/orchestrator`

## Requirements Mapping
- **R1. Dynamic Symbol Discovery**: Fetch all active USDT-M contract pairs from Weex (using suffix `_UMCBL`) and all configured exchanges in `.env`.
- **R2. Complete Unfiltered Scanning**: Scan all discovered pairs dynamically without pre-filtering, using a concurrency queue and rate-limiting handler (exponential back-off).
- **R3. API Endpoints & Telegram Commands**:
  - `GET /api/scan/all`: Triggers complete scan-all and returns ranked setups.
  - `/scan_all`: Telegram bot command executing scan and broadcasting top setups (Trend Template score >= 6 or VCP detected) to the Telegram chat.

## Key Files Identified
- `nerves/workers/trading/main.py`: FastAPI server entrypoint.
- `nerves/workers/trading/exchanges/weex_adapter.py`: Weex exchange adapter.
- `nerves/workers/trading/exchanges/binance_adapter.py`: Binance exchange adapter.
- `nerves/workers/trading/exchanges/bybit_adapter.py`: Bybit exchange adapter.
- `nerves/workers/trading/exchanges/registry.py`: Registry for active adapters.
- `nerves/workers/trading/analysis.py`: Main analysis logic (Trend Template and VCP).
- `nerves/workers/trading/config.py`: Environment configuration loader.
