# Cloudflare Worker — TradingView Webhook Proxy

Serverless proxy nhận webhook từ TradingView và forward qua Telegram Bot API.
PC nhà chỉ cần polling (outbound only) — **không cần tunnel, không mở port**.

## Architecture

```
TradingView Alert
      │ POST webhook
      ▼
Cloudflare Worker (edge, <50ms)
      │ verify secret
      │ forward payload
      ▼
Telegram Bot API (/signal command)
      │
      ▼ polling
PC Bot (telegram_bot.py)
      │ show confirm [✅/❌]
      ▼
Execute Trade (webhook_processor.py)
```

## Setup

### 1. Prerequisites

- [Node.js](https://nodejs.org/) v18+
- Cloudflare account (free): https://dash.cloudflare.com/sign-up

### 2. Install Wrangler CLI

```bash
cd worker
npm install
```

### 3. Login to Cloudflare

```bash
npx wrangler login
```

### 4. Set Secrets

```bash
# Webhook secret (same as WEBHOOK_SECRET in .env)
npx wrangler secret put WEBHOOK_SECRET

# Telegram Bot token (from @BotFather)
npx wrangler secret put TELEGRAM_TOKEN

# Telegram Chat ID
npx wrangler secret put TELEGRAM_CHAT_ID
```

### 5. Deploy

```bash
npx wrangler deploy
```

Output:
```
Published trading-webhook-proxy
  https://trading-webhook-proxy.YOUR-SUBDOMAIN.workers.dev
```

### 6. Configure TradingView Alert

In TradingView Alert settings:
- **Webhook URL**: `https://trading-webhook-proxy.YOUR-SUBDOMAIN.workers.dev`
- **Payload**:
```json
{
  "secret": "your_webhook_secret",
  "action": "{{strategy.order.action}}",
  "symbol": "{{ticker}}",
  "price": "{{close}}",
  "quoteQty": 50,
  "time": "{{timenow}}"
}
```

## Testing

### Local dev server
```bash
npx wrangler dev
# → http://localhost:8787
```

### Test with curl
```bash
curl -X POST https://trading-webhook-proxy.YOUR.workers.dev \
  -H "Content-Type: application/json" \
  -d '{
    "secret": "your_webhook_secret",
    "action": "buy",
    "symbol": "BTCUSDT",
    "price": "67500",
    "quoteQty": 50
  }'
```

### Expected response
```json
{
  "ok": true,
  "signal_forwarded": true,
  "symbol": "BTCUSDT",
  "action": "buy",
  "timestamp": "2026-05-04T09:30:00.000Z"
}
```

## Monitoring

```bash
# Real-time logs
npx wrangler tail

# Dashboard
# https://dash.cloudflare.com → Workers & Pages → trading-webhook-proxy
```

## Free Tier Limits

| Resource | Free Limit | Enough? |
|---|---|---|
| Requests/day | 100,000 | ✅ (trading signals ~10-50/day max) |
| CPU time/request | 10ms | ✅ (proxy takes <5ms) |
| Worker size | 1MB | ✅ (~2KB) |
