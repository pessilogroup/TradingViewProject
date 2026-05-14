# 🔴 [Bug] brief.py: TypeError - calls async function via asyncio.to_thread with wrong parameters

## Description

In `server/brief.py`, the `generate_morning_brief()` function calls `generate_trading_advice()` using `asyncio.to_thread()` with incorrect parameter names. This causes a `TypeError` crash.

## Location

**File:** `server/brief.py`, line ~190

## Current (Broken) Code

```python
ai_analysis = await asyncio.to_thread(
    generate_trading_advice,
    signal=signal_data,
    chunks=chunks,
    context_type="morning_brief"
)
```

## Problems

**Two separate issues:**

1. **Wrong invocation method:** `generate_trading_advice()` is defined as `async def` — it cannot be called via `asyncio.to_thread()` which expects a **synchronous** function. This will not execute the coroutine correctly.

2. **Wrong parameter names:** The actual function signature is:
   ```python
   async def generate_trading_advice(symbol, action, price, payload, rag_chunks)
   ```
   But it's called with `signal=..., chunks=..., context_type=...` — completely wrong keyword arguments → `TypeError`.

## Expected Fix

```python
# Option A: Call directly (since we're already in async context)
ai_analysis = await generate_trading_advice(
    symbol=", ".join(vcp_symbols) if vcp_symbols else "WATCHLIST",
    action="morning_brief",
    price="N/A",
    payload=signal_data,
    rag_chunks=chunks,
)
```

## Impact

- **Severity:** 🔴 Critical
- **Effect:** Morning Brief AI analysis section always fails with TypeError
- **User-facing:** Yes — morning brief is sent without AI analysis, or crashes entirely

## Steps to Reproduce

1. Enable `BRIEF_ENABLED=true` and `RAG_ENABLED=true`
2. Trigger morning brief via `/api/brief/trigger` or wait for scheduler
3. Brief crashes at RAG analysis step

## Labels

`bug`, `critical`, `morning-brief`
