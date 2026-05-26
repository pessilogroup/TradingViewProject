# BRIEFING — 2026-05-26T23:38:35+07:00

## Mission
Implement automated "Scan All" background feature for USDT-M futures on Weex (using suffix `_UMCBL`) and all configured exchanges.

## 🔒 My Identity
- Archetype: Feature Implementer
- Roles: implementer, qa, specialist
- Working directory: c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\worker_weex_7
- Original parent: 7efa8c3e-7692-4aaf-a41b-1289870f9172
- Milestone: Milestone 5: Automated "Scan All" background feature

## 🔒 Key Constraints
- USDT-M futures on Weex must use the suffix `_UMCBL`.
- Dynamic symbol discovery for active exchanges.
- Concurrent scanning with rate limit protection (100+ pairs).
- Expose `/api/scan/all` API endpoint and `/scan_all` Telegram bot command.
- Do not create git commits unless explicitly requested.

## Current Parent
- Conversation ID: 7efa8c3e-7692-4aaf-a41b-1289870f9172
- Updated: not yet

## Task Summary
- **What to build**: Automated background scanner for futures, API endpoint, and Telegram bot command integration.
- **Success criteria**:
  - Discover active symbols on Binance, Bybit, Weex dynamically.
  - Run concurrent scans safely under rate limits.
  - Expose API and Telegram command.
- **Interface contracts**: c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\orchestrator\PROJECT.md
- **Code layout**: nerves/workers/trading/

## Key Decisions Made
- [TBD]

## Artifact Index
- c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\worker_weex_7\original_prompt.md — Task description and parent messages.

## Change Tracker
- **Files modified**: None
- **Build status**: Untested
- **Pending issues**: None

## Quality Status
- **Build/test result**: Untested
- **Lint status**: Untested
- **Tests added/modified**: None

## Loaded Skills
- **Source**: C:\Users\pesil\.gemini\config\skills\angati-core-qa\SKILL.md
- **Local copy**: c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\worker_weex_7\angati-core-qa-SKILL.md
- **Core methodology**: QA skill for checking syntax, Ruff, AST security, auto-fixing issues, and validating core Python files.
