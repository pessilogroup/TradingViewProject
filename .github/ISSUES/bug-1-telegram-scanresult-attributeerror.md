# 🔴 [Bug] telegram_bot.py: AttributeError - treats ScanResult dataclass as dict

## Description

In `server/telegram_bot.py`, the `cmd_scan` function calls `.get()` on `ScanResult` dataclass objects, which causes an `AttributeError` crash.

## Location

**File:** `server/telegram_bot.py`, line ~261

## Current (Broken) Code

```python
for r in results:
    tt_score = r.get("trend_template", {}).get("score", "?")
    vcp = "⭐" if r.get("vcp", {}).get("detected") else ""
    vol_ratio = r.get("vcp", {}).get("volume_ratio", 0)
```

## Problem

`scan_symbols()` returns `list[ScanResult]` which are **dataclass objects**, NOT dicts. Calling `.get()` on a dataclass raises `AttributeError: 'ScanResult' object has no attribute 'get'`.

## Expected Fix

```python
for r in results:
    tt_score = r.trend_template.score
    vcp = "⭐" if r.vcp.detected else ""
    vol_ratio = r.vcp.volume_ratio
```

## Impact

- **Severity:** 🔴 Critical
- **Effect:** The `/scan` Telegram bot command crashes every time it is used
- **User-facing:** Yes — bot returns an error instead of scan results

## Steps to Reproduce

1. Enable Telegram bot and MCP
2. Send `/scan` command in Telegram
3. Bot crashes with `AttributeError`

## Labels

`bug`, `critical`, `telegram-bot`
