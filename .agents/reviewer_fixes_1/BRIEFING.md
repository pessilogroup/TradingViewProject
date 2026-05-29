# BRIEFING — 2026-05-26T17:00:00Z

## Mission
Verify code correctness, concurrency, task references, and HTML-escaping fixes for the "Scan All" background feature in TradingViewProject.

## 🔒 My Identity
- Archetype: reviewer_critic
- Roles: reviewer, critic
- Working directory: c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\reviewer_fixes_1
- Original parent: 7efa8c3e-7692-4aaf-a41b-1289870f9172
- Milestone: Scan All Verification
- Instance: 1 of 1

## 🔒 Key Constraints
- Review-only — do NOT modify implementation code
- Run build and tests to verify the work product, reporting any failures as findings — do NOT fix them yourself.

## Current Parent
- Conversation ID: 7efa8c3e-7692-4aaf-a41b-1289870f9172
- Updated: 2026-05-26T17:00:00Z

## Review Scope
- **Files to review**:
  - nerves/workers/trading/analysis.py
  - nerves/workers/trading/telegram_bot.py
- **Interface contracts**: c:\Users\pesil\working\mj_trading\TradingViewProject\PROJECT.md
- **Review criteria**: correctness, mock candles removal, concurrent fetching, background task reference, HTML escaping / sanitization.

## Review Checklist
- **Items reviewed**:
  - `analysis.py` (checked mock candle removal, concurrency pipeline, `VCPResult` instantiation)
  - `telegram_bot.py` (checked background scan strong references, HTML escaping / sanitization in `cmd_scan_all`/`cmd_scan_enhanced`, other commands escaping issues)
  - `notifier.py` (inspected regex translation from Markdown to HTML)
- **Verdict**: REQUEST_CHANGES (due to crashes on MCP errors in `analysis.py:209` and HTML formatting/escaping bugs in standard commands in `telegram_bot.py`)
- **Unverified claims**: None (all tested features and files verified)

## Attack Surface
- **Hypotheses tested**:
  - Mock candle fallback completely disabled -> verified via pytest failures/code logic
  - Background scan task uses module-level references to prevent garbage collection -> verified via `running_tasks` set
  - Concurrency bottlenecks -> verified concurrency is achieved via `asyncio.gather` and capped at 15 concurrent requests via `asyncio.Semaphore`
  - HTML escaping correctness -> found a bug where pre-built HTML tags get escaped into plain text in several commands
- **Vulnerabilities found**:
  - Crash/TypeError in `analysis.py` line 209: `VCPResult` instantiated with 5 arguments instead of 6, passing string `"Data unavailable"` to `vol_breakout` boolean field. Will cause a crash when MCP errors occur.
  - Escaped raw HTML tags in `telegram_bot.py` commands (`cmd_status`, `cmd_positions`, `cmd_trades`, `cmd_report`, `cmd_balance_enhanced`) rendering formatting inactive.
- **Untested angles**: None

## Key Decisions Made
- Inspected the whole codebase of target files and related modules (`notifier.py`, test files).
- Verified tests using background pytest run which executed 383 unit/stress/E2E tests successfully.

## Artifact Index
- c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\reviewer_fixes_1\handoff.md — Review Handoff Report
