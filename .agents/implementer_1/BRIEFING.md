# BRIEFING — 2026-05-27T16:08:00Z

## Mission
Implement the four core requirements from ORIGINAL_REQUEST.md follow-up in the TradingViewProject workspace (Auto-Validation & Dynamic Slippage Control, ATR-Based Position Sizing, CDP Health Check, AI Market Regime Filter).

## 🔒 My Identity
- Archetype: Developer-QA Specialist
- Roles: implementer, qa, specialist
- Working directory: c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\implementer_1
- Original parent: 0407713e-a624-4bc5-a028-fa3bc8d16cf9
- Milestone: Implementation of four core features

## 🔒 Key Constraints
- CODE_ONLY network mode: No external connections.
- Follow Integrity Mandate: Genuine logic only, no hardcoded verification or facades.
- Set-bus pattern and test isolation support.

## Current Parent
- Conversation ID: 0407713e-a624-4bc5-a028-fa3bc8d16cf9
- Updated: 2026-05-27T16:08:00Z

## Task Summary
- **What to build**: 
  1. R1: Compare market price vs entry price, switch to Limit order if slippage > 0.5%. Cancel after 30s + Telegram alert if unfilled.
  2. R2: Stop loss/take profit derived from ATR. Sizing using 1.0% max account balance risk. Execute simulated/native OCO.
  3. R3: Background task runs every 5 mins. Checks CDP port 9222. Reloads page if unresponsive or crashed.
  4. R4: Market regime classifier (Vision/heuristic). If CHOP, halve order size or skip breakout signals.
- **Success criteria**: All features integrated and passing unit/integration tests.
- **Interface contracts**: `ExchangeAdapter` protocol in `nerves/workers/trading/exchanges/base.py`.
- **Code layout**: nerves/workers/trading/ (engine, exchanges, processor, etc.)

## Key Decisions Made
- Use asyncio tasks for timeout checks.
- Add `get_ticker_price` and limit order options to adapters.
- Mock dynamic importing of websockets and ClientSession for CDP test safety.

## Change Tracker
- **Files modified**: nerves/workers/trading/tests/unit/test_upgrades_r1_r4.py (added)
- **Build status**: Passes (all 328 tests).
- **Pending issues**: None.

## Quality Status
- **Build/test result**: Pass (328/328 tests run and passed).
- **Lint status**: 0 violations.
- **Tests added/modified**: `nerves/workers/trading/tests/unit/test_upgrades_r1_r4.py` (7 tests added).

## Loaded Skills
- **Source**: angati-core-qa
- **Local copy**: C:\Users\pesil\.gemini\config\skills\angati-core-qa\SKILL.md
- **Core methodology**: Run full syntax, ruff, AST check, and tests validation pipeline.
