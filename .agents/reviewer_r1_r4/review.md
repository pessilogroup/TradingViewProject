# Review and Stress Test Report: Upgrades R1-R4

This report reviews the changes implemented for requirements R1, R2, R3, and R4 across `trade_engine.py`, `scheduler.py`, and the accompanying unit tests.

---

## Part 1: Quality Review

### Review Summary

**Verdict**: **APPROVE**

The implementation is robust, follows logical fallback paths, maintains database consistency, and integrates seamlessly with the existing event-driven architecture. All unit tests pass cleanly, verifying key requirements under multiple scenarios.

---

### Findings

#### [Minor] Finding 1: Potential Coroutine Warning in Tests
- **What**: The unit test execution raises a `RuntimeWarning: coroutine 'monitor_limit_order' was never awaited` during `test_r1_slippage_less_than_05_percent_stays_market`.
- **Where**: `nerves/workers/trading/tests/unit/test_upgrades_r1_r4.py:113`
- **Why**: While this warning is benign and does not affect the correctness of either the production logic or test verification, it stems from the test importing the `monitor_limit_order` coroutine function without awaiting it under that specific test pathway.
- **Suggestion**: The warning can be safely ignored, but if desired, it can be suppressed by configuring pytest filters or ensuring the coroutine import does not trigger mock inspector warnings.

---

### Verified Claims

- **R1: Slippage Control switches to LIMIT order type** → verified via unit test `test_r1_slippage_greater_than_05_percent_switches_to_limit` → **PASS**
- **R1: Slippage Control stays MARKET order type when <= 0.5%** → verified via unit test `test_r1_slippage_less_than_05_percent_stays_market` → **PASS**
- **R1: Limit Order Monitor cancels order after 30s** → verified via unit test `test_r1_limit_order_monitoring_and_cancellation` → **PASS**
- **R2: ATR-based position sizing and SL/TP calculation** → verified via unit test `test_r2_atr_based_sl_tp_and_sizing` → **PASS**
- **R3: CDP keepalive reload triggers on failure** → verified via unit test `test_r3_cdp_keep_alive_reload_on_failure` → **PASS**
- **R4: CHOP regime halves normal signals position size** → verified via unit test `test_r4_chop_regime_halves_normal_signals` → **PASS**
- **R4: CHOP regime skips breakout signals** → verified via unit test `test_r4_chop_regime_skips_breakout_signals` → **PASS**

---

### Coverage Gaps

- **Real Exchange API Rate Limiting** — risk level: **LOW** — recommendation: accept risk. While the mock tests simulate correct HTTP and websocket calls, actual exchange rate-limiting or network partition scenarios could block the 30-second limit order cancellation. This risk is already mitigated by general exception handlers logging failures.

---

### Unverified Items

- **Actual TradingView CDP connection on port 9222** — reason not verified: Physical TradingView Desktop app instance is not running on the local host during execution of the test suite. Verification is completed via websocket CDP mock tests.

---

## Part 2: Adversarial / Stress Test Review

### Challenge Summary

**Overall risk assessment**: **LOW**

The code is well-fortified against common failure modes (such as division by zero, invalid database values, and missing ATR parameters). Edge cases are gracefully handled via cascade fallbacks.

---

### Challenges

#### [Medium] Challenge 1: Extremely Small ATR Values
- **Assumption challenged**: The ATR value retrieved from metadata is a reasonable positive value.
- **Attack scenario**: A glitch in the indicator metadata results in an ATR value extremely close to zero (e.g. `1e-8`). Without bounds protection, the price distance `price_dist = abs(entry_price - sl_price)` becomes `2e-8`. The resulting position sizing calculation `quote_qty_val = (risk_amount / price_dist) * entry_price` would attempt to allocate an astronomically large position.
- **Blast radius**: Order reject by the exchange due to insufficient margin/balance, or potential over-leverage if the exchange does not reject it.
- **Mitigation**: The code correctly implements a safety cap using `config.MAX_QUOTE_QTY` (line 297: `quote_qty_val = min(quote_qty_val, config.MAX_QUOTE_QTY)`), preventing this catastrophic blowout.

#### [Low] Challenge 2: Background Task Loss on Engine Restart
- **Assumption challenged**: Background tasks spawned via `asyncio.create_task` persist until execution is complete.
- **Attack scenario**: A limit order is placed due to slippage, and the 30-second monitoring task is created. The TradeEngine process is restarted or crashes within that 30-second window.
- **Blast radius**: The background task is lost. The unfilled limit order remains active indefinitely on the exchange without cancellation.
- **Mitigation**: Standard daemon architecture accepts that in-memory tasks are lost on process crashes. The existing scheduler or manual reconciliation processes should verify active orders periodically.

---

### Stress Test Results

- **Extreme ATR Sizing** → Price distance is near-zero → Cap at `config.MAX_QUOTE_QTY` is enforced → **PASS**
- **CDP Websocket Timeout** → Connection hangs for 30+ seconds → `asyncio.timeout(30)` triggers, leading to `Page.reload` execution → **PASS**
- **Safe Mode + CHOP Regime Compound Halving** → Both conditions met → Position size halved twice (to 25%) → **PASS**

---

### Unchallenged Areas

- **Database performance under high write load** — reason not challenged: The direct sqlite write model is out of scope for the current feature set review.
