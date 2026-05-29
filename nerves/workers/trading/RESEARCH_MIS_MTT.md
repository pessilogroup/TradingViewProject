# Research: MIS & MTT Pine Script Indicators

> Generated: 2026-05-29  
> Source files: `pine/v2/a007_mis_webhook.pine`, `pine/v1/indicator_MTT_v1.001.pine`

---

## 1. MIS — "A.007 + MIS Combined" (1H Momentum)

### Pine Source: `pine/v2/a007_mis_webhook.pine`

**Strategy Type:** Overlay indicator + webhook alert dispatcher  
**Timeframe:** 1H (enforced by signal_processor.py)

### Indicators Computed
| Indicator | Period | Pine Code |
|-----------|--------|-----------|
| Fast EMA  | 20     | `ta.ema(close, 20)` |
| Slow EMA  | 50     | `ta.ema(close, 50)` |
| ATR       | 14     | `ta.atr(14)` |

### Signal Conditions
```pine
longCondition  = ta.crossover(fastEMA, slowEMA)  and barstate.isconfirmed
shortCondition = ta.crossunder(fastEMA, slowEMA) and barstate.isconfirmed

longExitCondition  = ta.crossunder(close, fastEMA) and barstate.isconfirmed
shortExitCondition = ta.crossover(close, fastEMA)  and barstate.isconfirmed
```

### Webhook Payload Fields
```json
{
  "secret": "<WEBHOOK_SECRET>",
  "source": "indicator",
  "indicator_name": "A.007 + MIS Combined",
  "symbol": "<ticker>",
  "signal_type": "entry" | "exit",
  "action": "buy" | "sell",
  "price": "<close>",
  "interval": "<timeframe.period>",
  "exchange": "<syminfo.prefix>",
  "confidence_score": 85,
  "metadata": {
    "direction": "long" | "short",
    "atr_value": "<atr>"
  }
}
```

### JS Replication Status: ✅ IMPLEMENTED
- `_calcMISSignals(times, closes)` in `dashboard-features.js`
- Uses EMA(20) crossover EMA(50) — matches Pine logic exactly
- Markers shown as orange arrows `[MIS]` on LightweightCharts

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

### VCP / Volume Dry-Up Detection
```pine
vol_sma    = ta.sma(volume, 50)
vol_dry_up = volume < (vol_sma * 0.5)          -- Volume < 50% of avg
tight_range = (high - low) < (atr * 0.5)       -- Tight candle range
vcp_signal = vol_dry_up and tight_range         -- VCP setup signal
```

### Regime Badge (Simplified for JS)
MTT uses SMA50/150/200 stack for regime detection:
```
TREND = price > SMA50 > SMA150 > SMA200  (bull stack)
CHOP  = anything else (bear/neutral stack)
```
**Implemented in:** `_csSetRegimeBadge(closes)` — shows `📈 TREND` or `⚡ CHOP` badge

### Why MTT Cannot Be Fully Replicated Client-Side
MTT **condition 8** requires:
```pine
bench_close = request.security(benchmark_ticker, timeframe.period, close)
stock_perf  = (close - close[125]) / close[125]
bench_perf  = (bench_close - bench_close[125]) / bench_close[125]
```
This calls `request.security()` to pull VNINDEX/SPY/BTCUSD data — **only available inside TradingView Pine Script**. 
A browser JS client would need a separate VNINDEX API call (not available on Binance), making full replication infeasible.

---

## 3. Data Flow

```
TradingView Alert
    ↓
POST /webhook  (gateway/webhook.py)
    ↓ validate secret, symbol, indicator_name
IndicatorSignalReceived event
    ↓
signal_processor.py
    - MIS: accepted only on 1H interval
    - MTT: blocked when regime = CHOP
    ↓
indicator_signals table (DB)
    ↓
GET /api/chart-markers  (NEW endpoint in main.py)
    ↓
LightweightCharts setMarkers()  [teal=MTT, orange=MIS]
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
| metadata | TEXT | JSON with `direction`, `atr_value` |
| interval | TEXT | `"60"` for 1H |
