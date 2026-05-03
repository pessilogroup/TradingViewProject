# 📈 TradingViewProject — Minervini SEPA Automated Trading System

> **Hệ thống giao dịch tự động** dựa trên phương pháp **Mark Minervini SEPA** — tích hợp Pine Script v5 Strategy với FastAPI Webhook Server để nhận tín hiệu từ TradingView, thực thi lệnh tự động trên Binance và gửi thông báo real-time qua Telegram/Discord.

## 🏗️ Kiến trúc Hệ thống

```
TradingView Alert → Cloudflare Tunnel → FastAPI Webhook (localhost:5000)
                                                  ├──► Binance API (Auto Trade)
                                                  └──► Telegram / Discord
```

## 📁 Cấu trúc Project

```
TradingViewProject/
├── pine/
│   ├── v1/                            # Legacy indicators
│   │   ├── minervini_trend_template.pine
│   │   ├── strategy_multi_indicator.pine
│   │   └── alert_webhook_v5.pine
│   └── v2/
│       └── minervini_strategy.pine    # ★ SEPA Strategy v2 (Backtestable)
├── server/
│   ├── main.py                        # FastAPI Webhook Server (Async)
│   ├── notifier.py                    # Telegram & Discord notifications
│   ├── config.py                      # Config loader (dotenv)
│   ├── requirements.txt
│   └── .env.example                   # Template cấu hình → copy sang .env
├── docs/
│   ├── TRADINGVIEW_ALERT_SETUP.md     # Hướng dẫn setup Alert
│   ├── plans/webhook_upgrade_fastapi.md
│   ├── doithu/fx_tactix_vs_our_project.md
│   └── knowledge/trading_wizard/      # Minervini RAG knowledge base
└── tradingview-mcp/                   # TradingView MCP integration (WIP)
```

---

## 🔥 Chiến lược Pine Script v2 — Minervini SEPA

File: `pine/v2/minervini_strategy.pine`

### 8 Tiêu chí Trend Template

| # | Điều kiện | Ý nghĩa |
|---|-----------|---------|
| 1 | Giá > SMA 150 & SMA 200 | Stage 2 uptrend confirmed |
| 2 | SMA 150 > SMA 200 | Momentum dài hạn tích cực |
| 3 | SMA 200 dốc lên (20 bars) | Xu hướng dài hạn tăng |
| 4 | SMA 50 > SMA 150 & SMA 200 | Momentum trung hạn tích cực |
| 5 | Giá > SMA 50 | Cổ phiếu mạnh hơn xu hướng trung hạn |
| 6 | Giá ≥ đáy 52 tuần × 1.30 | Không mua đáy, mua khi đã hồi phục |
| 7 | Giá ≥ đỉnh 52 tuần × 0.75 | Trong vòng 25% của đỉnh cao nhất |
| 8 | RS > Benchmark (BTC/SPY/VN) | Outperformance so với thị trường |

### VCP Breakout Detector

- **VCP Signal:** Volume < 50% trung bình + Biên độ hẹp (< 0.5× ATR)
- **Breakout:** Close vượt pivot với Volume > 1.5× trung bình
- **Entry:** Cả 8 tiêu chí + VCP Breakout + Heavy Volume hội tụ

### Risk Management

| Tham số | Mặc định | Ghi chú |
|---------|----------|---------|
| Stop Loss | 8% | Không vượt 10% |
| Take Profit | 20% | Risk/Reward ≥ 1:2.5 |
| Trailing Stop | SMA 50 | Cắt khi giá gãy MA50 với volume lớn |

---

## ⚙️ Webhook Server Setup

### 1. Cài đặt

```bash
cd server
pip install -r requirements.txt
cp .env.example .env
# Chỉnh sửa .env với thông tin thực
```

### 2. Chạy Server

```bash
python main.py
```

### 3. Cloudflare Tunnel

```bash
cloudflared tunnel --url http://localhost:5000
```

### 4. Test

```bash
# Health check
curl https://<random>.trycloudflare.com/tv_health_check

# Simulate TradingView alert
curl -X POST "https://<random>.trycloudflare.com/webhook" \
  -H "Content-Type: application/json" \
  -d '{"secret":"your_secret","action":"buy","symbol":"BTCUSDT","price":"68000","quoteQty":15}'
```

---

## 📲 TradingView Alert Payload

```json
{
  "secret": "your_super_secret_key",
  "action": "{{strategy.order.action}}",
  "symbol": "{{ticker}}",
  "price": "{{close}}",
  "quoteQty": 50,
  "time": "{{timenow}}"
}
```

Xem chi tiết: [`docs/TRADINGVIEW_ALERT_SETUP.md`](docs/TRADINGVIEW_ALERT_SETUP.md)

---

## 🗺️ Roadmap

- [x] Sprint 1: FastAPI Async + IP Whitelist middleware
- [x] Sprint 2: Dynamic order sizing + Async Binance
- [x] Sprint 3: Real-time Telegram/Discord notifications
- [x] Sprint 4: Trade Logging SQLite ✅
- [x] Sprint 5: TradingView MCP Integration ✅
- [x] Sprint 6: Performance Dashboard (Web UI) ✅

---

## 📚 References

- Mark Minervini — *Trade Like a Stock Market Wizard*
- Mark Minervini — *Think & Trade Like a Champion*
- [Pine Script v5 Manual](https://www.tradingview.com/pine-script-docs/)