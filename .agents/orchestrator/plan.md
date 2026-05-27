# Implementation Plan - Webhook Integration Extension (FastAPI + CDP + Risk + AI Regime)

## Tasks
1. **R1. Auto-Validation & Dynamic Slippage Control**:
   - Compare payload webhook `price` with real-time market price fetched from exchange (Binance / Weex / active exchange).
   - If slippage > 0.5%, place a LIMIT order instead of MARKET.
   - Wait up to 30 seconds for the Limit order to execute.
   - If not executed, cancel the order and send a Telegram warning notification "Slippage Warning".

2. **R2. ATR-Based Adaptive Position Sizing**:
   - Extract `atr_value` from payload webhook (check field/metadata).
   - Calculate Stop Loss = Entry Price - (2 * ATR) for Long / Entry Price + (2 * ATR) for Short.
   - Calculate trade sizing (`quoteQty`) so max loss is <= 1.0% of available account balance.
   - Place OCO order with the exact calculated SL and TP.

3. **R3. CDP Automatic Health Check & Keep-Alive**:
   - Add a background monitoring loop (running every 5 minutes).
   - Check if the TradingView tab is responsive/active (via CDP at port 9222).
   - If disconnected, hung, or unresponsive for 30 seconds, reload the TradingView tab via CDP.

4. **R4. AI Market Regime Filter**:
   - Before executing strategy signals, run a Gemini Vision check on chart screenshots or calculate a Heuristic from recent candle data to classify market regime as `TREND` or `CHOP` (Sideway).
   - If regime is `CHOP`, reduce position size by 50% or skip breakout breakout signals entirely.

## Strategy & Subagent Dispatch
We will dispatch a `teamwork_preview_worker` to explore the details of these files, write the implementations, and run tests.
We will first analyze how to test these components.
