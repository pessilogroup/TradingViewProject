# TradingView Multi-Indicator Strategy

Pine Script v5 strategy + Python webhook server for automated crypto trading.

## Project Structure

```
TradingViewProject/
├── pine/
│   └── strategy_multi_indicator.pine   # TradingView strategy
└── server/
    ├── main.py                          # Flask webhook server
    ├── config.py                        # Config loader
    └── requirements.txt
```

---

## Pine Script Setup

1. Open [TradingView](https://www.tradingview.com) → Pine Editor (bottom panel)
2. Copy the contents of `pine/strategy_multi_indicator.pine` and paste it
3. Click **Add to chart**
4. Run backtest on **BTCUSDT / 1H** or **15m**

### Strategy Logic

| Signal | Conditions |
|--------|-----------|
| **Long** | EMA20 > EMA50 > EMA200, RSI 50–70, MACD cross up, Volume spike |
| **Short** | EMA20 < EMA50 < EMA200, RSI 30–50, MACD cross down, Volume spike |
| **Stop Loss** | 2× ATR below/above entry |
| **Take Profit** | 3× ATR above/below entry |

---

## Webhook Server Setup

### 1. Install dependencies

```bash
cd server
pip install -r requirements.txt
```

### 2. Create `.env` file

```env
WEBHOOK_SECRET=your_secret_token_here
PORT=5000
DEBUG=false

# Optional — Binance auto-order
BINANCE_API_KEY=
BINANCE_API_SECRET=
BINANCE_TESTNET=true
```

### 3. Run server

```bash
python main.py
```

### 4. Test endpoints

```bash
# Health check
curl http://localhost:5000/tv_health_check

# Simulate TradingView alert
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -H "X-TV-Secret: your_secret_token_here" \
  -d '{"action":"buy","symbol":"BTCUSDT","price":"65000","time":"2026-04-28T10:00:00Z"}'
```

---

## TradingView Alert Configuration

1. On the chart, right-click → **Add Alert**
2. Set condition to trigger on strategy entry signals
3. Under **Notifications** → enable **Webhook URL**
4. URL: `http://<your-server-ip>:5000/webhook`
5. Add header: `X-TV-Secret` = your secret token
6. Message body (JSON):
   ```json
   {"action":"{{strategy.order.action}}","symbol":"{{ticker}}","price":"{{close}}","time":"{{time}}"}
   ```
