# 🛡️ Mini-MDASH Security Report

**Target**: `C:\Users\pesil\working\mj_trading\TradingViewProject\server`
**Timestamp**: 2026-05-14T21:43:39.940449+00:00
**Files Scanned**: 21

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | **4** |
| 🟠 High | **4** |
| 🟡 Medium | **6** |
| 🟢 Low | **1** |
| ℹ️ Info | **0** |
| **Total** | **15** |

**Scanners**: secret-detector, tvp-trading-rules, static-analysis

> **VERDICT: 🔴 CRITICAL — Immediate action required**

## Findings

### 🔴 CRITICAL

#### [TVP-002] Uncapped trade size from webhook payload
- **File**: `TradingViewProject/server/main.py` (line 432)
- **Confidence**: 90%
- **CWE**: [CWE-770](https://cwe.mitre.org/data/definitions/770.html)
- **Description**: quoteQty is extracted from webhook payload without a maximum cap. An attacker who compromises the webhook secret could submit a trade with quoteQty=999999, draining the Binance account.
- **Evidence**: `quote_qty = payload.get('quoteQty', ...)`
- **Fix**: Add MAX_QUOTE_QTY config (e.g., 100 USDT) and clamp: quote_qty = min(float(quote_qty), config.MAX_QUOTE_QTY)

#### [SEC-001] Potential Telegram Bot Token in .env
- **File**: `TradingViewProject/server/.env` (line 41)
- **Confidence**: 75%
- **CWE**: [CWE-798](https://cwe.mitre.org/data/definitions/798.html)
- **Description**: Detected what appears to be a Telegram Bot Token in configuration file.
- **Evidence**: `TELEGRAM_BOT_TOKEN=8602739357:AAGMPw6IXR... (value redacted)`
- **Fix**: Move to a secrets manager or ensure this file is in .gitignore. Never commit real credentials to version control.

#### [SEC-001] Potential API key in .env
- **File**: `TradingViewProject/server/.env` (line 69)
- **Confidence**: 75%
- **CWE**: [CWE-798](https://cwe.mitre.org/data/definitions/798.html)
- **Description**: Detected what appears to be a API key in configuration file.
- **Evidence**: `GEMINI_API_KEY=AIzaSyDXtytTwJ5InxL6dOaSq... (value redacted)`
- **Fix**: Move to a secrets manager or ensure this file is in .gitignore. Never commit real credentials to version control.

#### [SEC-001] Potential Telegram Bot Token in .env
- **File**: `mj_trading/TradingViewProject/.env` (line 41)
- **Confidence**: 75%
- **CWE**: [CWE-798](https://cwe.mitre.org/data/definitions/798.html)
- **Description**: Detected what appears to be a Telegram Bot Token in configuration file.
- **Evidence**: `TELEGRAM_BOT_TOKEN=8602739357:AAGMPw6IXR... (value redacted)`
- **Fix**: Move to a secrets manager or ensure this file is in .gitignore. Never commit real credentials to version control.

### 🟠 HIGH

#### [TVP-001] Unsafe price/qty parsing without try/except
- **File**: `TradingViewProject/server/main.py` (line 456)
- **Confidence**: 80%
- **CWE**: [CWE-20](https://cwe.mitre.org/data/definitions/20.html)
- **Description**: float() called on user-controlled variable 'quote_qty' without try/except guard. A non-numeric webhook payload will crash the handler.
- **Evidence**: `quote_qty=float(quote_qty) if quote_qty else None,`
- **Fix**: Wrap in try/except (ValueError, TypeError) with safe default.

#### [TVP-001] Unsafe price/qty parsing without try/except
- **File**: `TradingViewProject/server/main.py` (line 759)
- **Confidence**: 80%
- **CWE**: [CWE-20](https://cwe.mitre.org/data/definitions/20.html)
- **Description**: float() called on user-controlled variable 'quote_qty' without try/except guard. A non-numeric webhook payload will crash the handler.
- **Evidence**: `requested_qty=float(quote_qty) if quote_qty else 0,`
- **Fix**: Wrap in try/except (ValueError, TypeError) with safe default.

#### [TVP-007] Telegram bot token potentially exposed in error output
- **File**: `TradingViewProject/server/telegram_bot.py` (line 622)
- **Confidence**: 70%
- **CWE**: [CWE-532](https://cwe.mitre.org/data/definitions/532.html)
- **Description**: Telegram bot token referenced in logging/error handling code. If the token value is interpolated into the message, it will appear in trades.log and could be exfiltrated.
- **Evidence**: `log.warning("TELEGRAM_BOT_TOKEN not set — Telegram Bot disabled")`
- **Fix**: Never log token values. Log only 'token_present=True/False'.

#### [SEC-001] Potential Hardcoded secret/password in simulate_webhook.ps1
- **File**: `TradingViewProject/server/simulate_webhook.ps1` (line 11)
- **Confidence**: 75%
- **CWE**: [CWE-798](https://cwe.mitre.org/data/definitions/798.html)
- **Description**: Detected what appears to be a Hardcoded secret/password in configuration file.
- **Evidence**: `$Secret = "7086c59c523e87c90f9d56db63a66... (value redacted)`
- **Fix**: Move to a secrets manager or ensure this file is in .gitignore. Never commit real credentials to version control.

### 🟡 MEDIUM

#### [TVP-005] Potential path traversal in screenshot save path
- **File**: `TradingViewProject/server/brief.py` (line 132)
- **Confidence**: 60%
- **CWE**: [CWE-22](https://cwe.mitre.org/data/definitions/22.html)
- **Description**: File save path may incorporate user-controlled data (symbol from webhook). A crafted symbol like '../../etc/passwd' could write outside the screenshots dir.
- **Evidence**: `save_path=Path(__file__).parent / "screenshots" / f"brief_{top.symbol}_{timestamp.strftime('%Y%m%d')`
- **Fix**: Sanitize symbol name: symbol = re.sub(r'[^A-Za-z0-9]', '', symbol)

#### [TVP-004] No rate limiting on API endpoints
- **File**: `TradingViewProject/server/main.py` (line 169)
- **Confidence**: 95%
- **CWE**: [CWE-770](https://cwe.mitre.org/data/definitions/770.html)
- **Description**: Found 28 API endpoints with no rate limiting middleware. An attacker can flood /webhook with thousands of requests to exhaust Binance API quota or trigger unwanted trades.
- **Evidence**: `Endpoints: GET /health, GET /dashboard, GET /, GET /tv_health_check, GET /api/mcp/status`
- **Fix**: Add slowapi or custom rate limiter middleware (e.g., 10 req/min on /webhook).

#### [TVP-005] Potential path traversal in screenshot save path
- **File**: `TradingViewProject/server/main.py` (line 576)
- **Confidence**: 60%
- **CWE**: [CWE-22](https://cwe.mitre.org/data/definitions/22.html)
- **Description**: File save path may incorporate user-controlled data (symbol from webhook). A crafted symbol like '../../etc/passwd' could write outside the screenshots dir.
- **Evidence**: `save_path = Path(__file__).parent / "screenshots" / f"stealth_{symbol}_{ts_str}.png"`
- **Fix**: Sanitize symbol name: symbol = re.sub(r'[^A-Za-z0-9]', '', symbol)

#### [TVP-005] Potential path traversal in screenshot save path
- **File**: `TradingViewProject/server/mcp_client.py` (line 239)
- **Confidence**: 60%
- **CWE**: [CWE-22](https://cwe.mitre.org/data/definitions/22.html)
- **Description**: File save path may incorporate user-controlled data (symbol from webhook). A crafted symbol like '../../etc/passwd' could write outside the screenshots dir.
- **Evidence**: `save_path = Path(__file__).parent / "screenshots" / f"{symbol}_{timeframe}.png"`
- **Fix**: Sanitize symbol name: symbol = re.sub(r'[^A-Za-z0-9]', '', symbol)

#### [TVP-005] Potential path traversal in screenshot save path
- **File**: `TradingViewProject/server/telegram_bot.py` (line 357)
- **Confidence**: 60%
- **CWE**: [CWE-22](https://cwe.mitre.org/data/definitions/22.html)
- **Description**: File save path may incorporate user-controlled data (symbol from webhook). A crafted symbol like '../../etc/passwd' could write outside the screenshots dir.
- **Evidence**: `save_path=screenshots_dir / f"vision_{symbol}_{dt.now().strftime('%Y%m%d_%H%M%S')}.png"`
- **Fix**: Sanitize symbol name: symbol = re.sub(r'[^A-Za-z0-9]', '', symbol)

#### [STA-001] Dynamic import — potential code injection
- **File**: `TradingViewProject/server/mcp_client.py` (line 71)
- **Confidence**: 90%
- **CWE**: [CWE-502](https://cwe.mitre.org/data/definitions/502.html)
- **Description**: Call to __import__() detected. This can execute arbitrary code.
- **Evidence**: `__import__(...) at line 71`
- **Fix**: Remove __import__() or use a safe alternative.

### 🟢 LOW

#### [TVP-006] DRY_RUN mode overridable via environment variable
- **File**: `TradingViewProject/server/config.py` (line 25)
- **Confidence**: 50%
- **CWE**: [CWE-1188](https://cwe.mitre.org/data/definitions/1188.html)
- **Description**: BINANCE_DRY_RUN is loaded from environment at startup. If .env file is writable or env can be injected, an attacker could disable dry-run mode and execute real trades.
- **Evidence**: `BINANCE_DRY_RUN    = os.getenv("BINANCE_DRY_RUN", "true").lower() == "true"`
- **Fix**: Add runtime validation: if production, force DRY_RUN=true unless explicit unlock.

---
*Generated by Mini-MDASH Security Harness v1.0 — 2026-05-14T21:43:39.940449+00:00*