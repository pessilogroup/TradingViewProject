# Research: MIS & MTT Pine Script Indicators

> Generated: 2026-05-30 (Updated v3)
> Source files: `pine/v2/a007_mis_webhook.pine`, `pine/v1/indicator_MTT_v1.001.pine`

---

## 1. MIS — "MIS(A7-01B.V3) Webhook" (Multi-Timeframe Momentum)

### Pine Source: `pine/v2/a007_mis_webhook.pine`

**Type:** Pure indicator (not strategy) — Pine v6
**Timeframe:** Adaptive — works on 1m/3m/5m/15m/30m/1H/4H

### Indicators Computed
| Indicator | Period | Notes |
|-----------|--------|-------|
| Fast EMA  | Adaptive | 5m=5, 15m=8, 30m=12, 1H=20 |
| Slow EMA  | Adaptive | 5m=13, 15m=21, 30m=34, 1H=50 |
| ATR       | 14     | Used for SL/TP calculation |
| RSI       | 14     | Displayed in status table |
| Daily EMA 20/50 | MTF | via `request.security("D")` |
| 1H EMA 20/50    | MTF | via `request.security("60")` |

### Signal Conditions
```pine
longCondition  = ta.crossover(fastEMA, slowEMA)  and barstate.isconfirmed
shortCondition = ta.crossunder(fastEMA, slowEMA) and barstate.isconfirmed

longExitCondition  = ta.crossunder(close, fastEMA) and barstate.isconfirmed
shortExitCondition = ta.crossover(close, fastEMA)  and barstate.isconfirmed
```

### SL/TP Auto-Draw
```pine
SL = entry_price +/- ATR * atrSlMul  (default 2.0, configurable)
TP = entry_price +/- ATR * atrTpMul  (default 4.0, configurable)
```
Lines drawn as dashed red (SL) and green (TP), cleared on exit.

### Visual Toggles (all in Settings)
| Toggle | Default | Description |
|--------|---------|-------------|
| EMA Ribbon | ON | Fast/Slow EMA + fill |
| MTF Daily | ON | Daily EMA 20/50 (purple stepline) |
| MTF 1H | ON | 1H EMA 20/50 (cyan stepline) |
| SL/TP Lines | ON | Auto SL/TP on entry |
| Entry/Exit Markers | ON | L/S labels + x-cross |
| Status Table | ON | Top-right info panel |
| Background Flash | OFF | Bg color on entry |

### Alert System (Dual)
1. **Auto webhook**: `alert()` sends JSON payload on every signal
2. **Manual alertcondition**: 4 conditions available in TradingView Alert UI

### Webhook Payload Fields (v3)
```json
{
  "secret": "<WEBHOOK_SECRET>",
  "source": "indicator",
  "indicator_name": "MIS(A7-01B.V3)",
  "symbol": "<ticker>",
  "signal_type": "entry" | "exit",
  "action": "buy" | "sell",
  "price": "<close>",
  "interval": "<timeframe.period>",
  "exchange": "<syminfo.prefix>",
  "confidence_score": 85,
  "metadata": {
    "direction": "long" | "short",
    "atr_value": "<atr>",
    "sl": "<stop_loss_price>",
    "tp": "<take_profit_price>"
  }
}
```

### JS Replication Status: PARTIAL
- `_calcMISSignals(times, closes)` in `dashboard-features.js` uses EMA(20)/EMA(50)
- Needs update to match adaptive periods per timeframe
- MTF lines cannot be replicated client-side (no Daily data on Binance WS)

---

## 2. MTT — "Minervini Trend Template" (Daily)

### Pine Source: `pine/v1/indicator_MTT_v1.001.pine`

**Strategy Type:** Trend quality filter — NOT a signal generator
**Timeframe:** Daily (designed for D timeframe)
**Purpose:** Identifies stocks/assets in a strong uptrend using Mark Minervini's 8-condition Trend Template

### Indicators Computed
| Indicator | Period | Pine Code |
|-----------|--------|-----------|
| SMA 50    | 50     | `ta.sma(close, 50)` |
| SMA 150   | 150    | `ta.sma(close, 150)` |
| SMA 200   | 200    | `ta.sma(close, 200)` |
| 52W High  | 250    | `ta.highest(high, 250)` |
| 52W Low   | 250    | `ta.lowest(low, 250)` |
| RS        | 125    | vs. benchmark (VNINDEX/SPY/BTC) |

### 8 Trend Template Conditions
```pine
cond1 = close > sma150 and close > sma200          -- Price above key MAs
cond2 = sma150 > sma200                             -- MA alignment
cond3 = sma200 > sma200[20]                         -- SMA200 trending up
cond4 = sma50 > sma150 and sma50 > sma200          -- SMA50 leading
cond5 = close > sma50                               -- Price above fast MA
cond6 = close >= (low52 * 1.30)                     -- >30% above 52W low
cond7 = close >= (high52 * 0.75)                    -- within 25% of 52W high
cond8 = stock_perf > bench_perf                     -- Outperforming benchmark

trend_template_met = cond1 and cond2 and cond3 and cond4 and cond5 and cond6 and cond7 and cond8
```

### Regime Badge (Simplified for JS)
MTT uses SMA50/150/200 stack for regime detection:
```
TREND = price > SMA50 > SMA150 > SMA200  (bull stack)
CHOP  = anything else (bear/neutral stack)
```

---

## 3. Data Flow (v3)

```
TradingView indicator MIS(A7-01B.V3)
    |
    |-- alert() [auto webhook]
    |-- alertcondition() [manual alerts]
    |
    v
POST /webhook  (gateway/webhook.py)
    | validate secret, symbol, indicator_name
    v
IndicatorSignalReceived event
    |
    v
signal_processor.py
    - Accepts: 5m/15m/30m/1H intervals
    - Rejects: CHOP regime for Daily MTT
    |
    v
indicator_signals table (DB)
    |
    v
GET /api/chart-markers + GET /api/indicator-signals
    |
    v
Dashboard: LightweightCharts markers + Signals tab
```

---

## 4. DB Schema Relevant Fields

### `signals` table
| Column | Type | Notes |
|--------|------|-------|
| mode   | TEXT | `"MTT"` or `"MIS"` |
| action | TEXT | `"buy"` or `"sell"` |
| price  | REAL | Entry price |
| payload | TEXT | JSON blob with confidence_score |

### `indicator_signals` table
| Column | Type | Notes |
|--------|------|-------|
| signal_type | TEXT | `"entry"` or `"exit"` |
| confidence_score | INT | 0-100 |
| metadata | TEXT | JSON with `direction`, `atr_value`, `sl`, `tp` |
| interval | TEXT | `"5"`, `"15"`, `"30"`, `"60"` |

---

## 5. Version History

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | 2026-05 | Original EMA 20/50 strategy, 1H only |
| v2.1 | 2026-05-30 | Adaptive EMA, compact visual, strategy |
| **v3.0** | **2026-05-30** | **Pine v6, indicator(), MTF Daily+1H EMA, SL/TP lines, dual alerts, all toggleable** |
