# 🟡 [Bug] binance_client.py: Dry-run mode uses hardcoded mock price $67,500

## Description

In `server/binance_client.py`, the dry-run mode always returns a hardcoded fill price of `67500.0` regardless of the actual symbol or entry price. This makes dry-run simulations inaccurate for all non-BTC assets.

## Location

**File:** `server/binance_client.py`, line ~186

## Current (Broken) Code

```python
# In place_market_order, DRY_RUN branch:
fill_price = 67500.0  # Mock price
```

## Problem

When executing a dry-run order for any symbol (e.g., ETHUSDT at $3,500 or SOLUSDT at $150), the mock fill price is always `$67,500`. This causes:

1. **Incorrect SL/TP calculation** — `execute_smart_order` recalculates SL/TP based on the mock fill price when it differs from the alert entry price
2. **Misleading notifications** — Telegram messages show wrong execution price
3. **Inaccurate simulation** — Defeats the purpose of dry-run testing

## Expected Fix

```python
# Use the actual entry_price or a reasonable estimate
fill_price = entry_price if entry_price > 0 else quote.close
```

Or pass the entry price through to the dry-run response:

```python
fill_price = float(params.get("price_hint", 67500.0))
```

## Impact

- **Severity:** 🟡 Medium
- **Effect:** Dry-run mode produces inaccurate simulations
- **User-facing:** Yes — misleading trade notifications in DRY_RUN mode

## Steps to Reproduce

1. Set `BINANCE_DRY_RUN=true`
2. Send a webhook alert for ETHUSDT at price 3500
3. Observe fill price reported as 67500.0 in logs/Telegram

## Labels

`bug`, `medium`, `binance`
