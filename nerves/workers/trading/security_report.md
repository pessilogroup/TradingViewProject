# Mini-MDASH Security Report

**Target**: `server/` (project root scan: `python -m security.cli scan --target .` from `server` directory)  
**Timestamp**: 2026-05-15 (see `security_report.json` for exact ISO time)  
**Files scanned**: 45  

## Summary (latest JSON)

| Severity  | Count |
|-----------|-------|
| Critical  | 0     |
| High      | 0     |
| Medium    | 1     |
| Low       | 1     |
| **Total** | **2** |

**Scanners used (this run)**: `tvp-trading-rules` only produced findings; static, dependency, and secret scanners ran with zero additional findings in the committed report artifact.

**Verdict**: No critical or high findings from the trading-rules scan. Address medium/low or accept documented risk.

---

## Current findings (machine-readable copy)

Full payload: [security_report.json](security_report.json).

### TVP-004 — Medium — No global rate limiting on API endpoints

- **File**: [main.py](main.py) (first registered route line ~196)
- **Description**: FastAPI routes defined on `app` in `main.py` have no app-wide rate limiter (e.g. slowapi). Authenticated or expensive routes could be abused for DoS or quota burn.
- **Mitigation already in place**: `POST /webhook` is rate-limited per source IP (15/min) in [gateway/webhook.py](gateway/webhook.py) (`_WEBHOOK_RATE_LIMITS`, HTTP 429).
- **Remediation**: Add per-route or global limits for `/api/*`, `/trades`, etc.

### TVP-006 — Low — DRY_RUN from environment

- **File**: [config.py](config.py)
- **Description**: `BINANCE_DRY_RUN` comes from env; combined with `ENVIRONMENT` / `FORCE_LIVE_TRADING` there is already a production guard — residual risk is host compromise of `.env` or process env.
- **Remediation**: Keep secrets on host out of SCM; optional stricter policy (e.g. refuse live without explicit operator flag).

---

## Triage: superseded or clarified items (older report cycles)

These appeared in historical `security_report.json` / harness output before the webhook moved to `gateway/webhook.py` and parsers were hardened.

| ID / theme | Prior claim | Status | Evidence |
|------------|-------------|--------|----------|
| TVP-002 | Uncapped `quoteQty` on webhook | **Mitigated** | [gateway/webhook.py](gateway/webhook.py): `quote_qty_val = min(quote_qty_val, config.MAX_QUOTE_QTY)` after safe float parse; [config.py](config.py) `MAX_QUOTE_QTY`. |
| TVP-001 | Unsafe `float()` on webhook fields | **Mitigated** | Same file: try/except for `price` and `quote_qty` with safe defaults. |
| TVP-004 (old text) | “Flood `/webhook`” with no RL | **Clarified** | Webhook RL lives in gateway module; remaining gap is **other** routes in `main.py`. |
| TVP-005 | Path traversal in screenshot paths | **Mitigated / false positive** | [brief.py](brief.py), [telegram_bot.py](telegram_bot.py), [analyzer/ai_analyzer.py](analyzer/ai_analyzer.py): `safe_symbol` via `re.sub` before filename; scanner updated to skip lines containing `safe_symbol`. |
| SEC-001 | Secrets in `.env` / scripts | **Operational** | Keep `.env` and local scripts out of git; rotate if ever committed. Re-run secret scanner on CI with a clean tree. |
| TVP-007 | Telegram token in logs | **Low / wording** | Code references the **name** `TELEGRAM_BOT_TOKEN` in a static message, not the secret value; optional copy change to “Telegram credentials not configured”. |

---

## Manual review (2026-05-15)

1. **Webhook HMAC-style compare**: [gateway/webhook.py](gateway/webhook.py) uses `secrets.compare_digest(str(secret), str(config.WEBHOOK_SECRET))` for non-dashboard callers (dashboard still uses Bearer `DASHBOARD_TOKEN` bypass by design).
2. **Dashboard bypass**: Valid `Authorization: Bearer <DASHBOARD_TOKEN>` skips webhook secret — treat `DASHBOARD_TOKEN` like a root credential; HTTPS and rotation required.
3. **Default `WEBHOOK_SECRET`**: [config.py](config.py) default `change_me_in_dotenv` must be overridden in production.
4. **`X-Forwarded-For`**: [main.py](main.py) and webhook use first forwarded hop for IP-derived limits/whitelist — only safe behind a trusted reverse proxy.
5. **SQL**: Grep of [telegram_bot.py](telegram_bot.py) found no `execute(f"...")` patterns; keep new queries parameterized.
6. **MCP subprocess**: [mcp_client.py](mcp_client.py) uses `asyncio.create_subprocess_exec` without shell; CLI args include symbol/timeframe from callers — acceptable today; consider strict allowlist if inputs widen.

---

## Regression checks

- `python -m pytest tests/security/ tests/integration/test_webhook.py` — all passed after webhook digest change.
- Re-run harness: `python -m security.cli scan --target . --format json --output security_report.json`

---

*Generated / refreshed as part of the security bug finding plan. Mini-MDASH harness: [security/harness.py](security/harness.py).*
