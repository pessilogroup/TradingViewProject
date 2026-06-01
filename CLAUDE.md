# TradingViewProject (Client Project) - Sovereign Rules

## 🛡️ SSoT Boundary & Isolation (The Zero-Flood Guarantee)
- **Status:** Client Project (ISOLATED)
- **CRITICAL DIRECTIVE:** Do NOT inject any logs, backtests, or code structure from this project into the global EAIS `conv_graph.db` or global Angati Qdrant instance. All Semantic Mapping and Knowledge Graph operations MUST target local isolated DBs if executed.

## 📂 Context Locations
- **Pine Script logic:** `pine/v1/`, `pine/v2/`
- **Backtest Reports:** `docs/reports/`
- **Trading Methods:** `docs/references/`
- **Core Server:** `server/`

## 🔌 MCP Servers
- `tradingview` MCP is registered globally. Requires TradingView Desktop running on CDP port 9222. Use `/tv-start` to initialize.

## 🤖 Workflows
- When doing analysis on `docs/reports`, rely on Local RAG (ChromaDB in `server/rag.py`) or direct reading, NOT the global EAIS Hippocampus.
