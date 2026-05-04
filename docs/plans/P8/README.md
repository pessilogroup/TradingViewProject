# P8: Cloudflare Worker → Telegram Bot (Zero Tunnel)

## Mục tiêu
Loại bỏ Cloudflare Tunnel (`cloudflared`) — thay bằng Cloudflare Worker serverless
proxy, forward webhook qua Telegram Bot API. PC nhà chỉ cần outbound connection.

## Architecture

```
TRƯỚC:  TradingView → cloudflared tunnel → PC:5000/webhook
SAU:    TradingView → CF Worker (edge) → Telegram API → PC polls → process
```

## Components

### 1. `server/webhook_processor.py` (NEW)
- Extract webhook logic từ `main.py`
- 2 functions: `save_signal()` + `execute_signal()`
- `process_webhook_signal()` = combined (backward compat cho FastAPI)

### 2. `server/telegram_bot.py` (MODIFIED)
- `/signal` command: nhận JSON payload từ CF Worker
- Confirmation flow: `[✅ Execute] [❌ Cancel]` inline keyboard
- `signal_confirm_callback`: handle button press
- Security: verify `WEBHOOK_SECRET` + `TELEGRAM_CHAT_ID`

### 3. `worker/` (NEW)
- Cloudflare Worker ~110 lines JS
- Verify secret → forward to Telegram Bot API
- Deploy: `npx wrangler deploy`
- Free tier: 100K req/day

### 4. `server/main.py` (MODIFIED)
- `/webhook` endpoint refactored to use `webhook_processor`
- Backward compatible cho VPS deploy

## Signal Flow (with Confirmation)

```
TradingView Alert
    │
    ▼ POST
CF Worker (verify secret)
    │
    ▼ /signal {json}
Telegram Bot API
    │
    ▼ polling
telegram_bot.py → cmd_signal()
    │
    ├── 1. save_signal() → DB + RAG analysis
    │
    ├── 2. Show confirmation:
    │     📡 Signal #42 [DRY-RUN]
    │     - Symbol: BTCUSDT
    │     - Action: BUY
    │     - Price: $67,500
    │     [✅ Execute] [❌ Cancel]
    │
    └── 3a. User taps ✅ → execute_signal() → Binance OCO
        3b. User taps ❌ → cancel, update DB status
```

## Remote Dashboard Access
- **Tailscale** (free mesh VPN): install trên PC + phone
- Truy cập `http://100.x.x.x:5000/dashboard` từ mọi nơi
- Không cần mở port, không cần tunnel

## Config

```env
# .env
WORKER_WEBHOOK_ENABLED=true
```

## Sprint Status: ✅ Completed
- [x] webhook_processor.py
- [x] telegram_bot.py /signal + confirm
- [x] Cloudflare Worker
- [x] Config updates
- [x] Documentation
