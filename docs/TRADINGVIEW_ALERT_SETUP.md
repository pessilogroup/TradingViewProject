# TradingView Alert → Flask Webhook Setup

End-to-end flow:

```
TradingView Alert  →  Cloudflare Tunnel  →  localhost:5000/webhook  →  trades.log (+ optional Binance)
```

## 1. Cloudflared tunnel (Quick Tunnel)

A Quick Tunnel is ephemeral — the public URL changes every time you restart it. Good enough to develop with. Pin a permanent URL by registering a domain through Cloudflare and using `cloudflared tunnel create`.

Run from any terminal:
```
cloudflared tunnel --url http://localhost:5000
```

Look for a line like:
```
https://<random-words>.trycloudflare.com
```

Sanity check:
```
curl https://<random-words>.trycloudflare.com/tv_health_check
```

## 2. Webhook secret

The current server reads `WEBHOOK_SECRET` from `server/.env`. TradingView **cannot** send custom HTTP headers, so the server accepts the secret in three places (any one is enough):

| Location | Example |
|----------|---------|
| Header | `X-TV-Secret: <secret>` (only useful when calling manually with curl) |
| Query string | `https://<tunnel>/webhook?secret=<secret>` |
| JSON body | `{ "secret": "<secret>", "action": "buy", ... }` (recommended for TradingView) |

## 3. Pine Script

Use [`pine/alert_webhook_v5.pine`](../pine/alert_webhook_v5.pine). Replace `REPLACE_WITH_WEBHOOK_SECRET` in both `alertcondition` messages with the actual secret from `server/.env` before saving the indicator on TradingView.

Workflow:
1. Open Pine Editor in TradingView
2. Paste the script, save, add to chart
3. Right-click chart → Add alert
4. **Condition**: the indicator name → choose "Long Cross" or "Short Cross"
5. **Webhook URL**: `https://<random>.trycloudflare.com/webhook`
6. **Message**: leave default — Pine `alertcondition` already provides the JSON template
7. Trigger: "Once Per Bar Close"
8. Create

## 4. Manual end-to-end test

Replace the URL and secret with yours:
```
curl -X POST "https://<random>.trycloudflare.com/webhook" \
  -H "Content-Type: application/json" \
  -d '{"secret":"<WEBHOOK_SECRET>","action":"buy","symbol":"BINANCE:BTCUSDT","price":"68000","time":"2026-04-28T11:00:00Z"}'
```

Expected response:
```
{"received": true, "order": null}
```

Then check `server/trades.log`:
```
ALERT  action=buy  symbol=BINANCE:BTCUSDT  price=68000  time=2026-04-28T11:00:00Z
```

## 5. Troubleshooting

| Symptom | Cause / Fix |
|---------|-------------|
| `401 unauthorized` | Secret mismatch — recheck `WEBHOOK_SECRET` in `.env` vs the value baked into the Pine Script `alertcondition` |
| TradingView "Webhook URL must be HTTPS" | Use the trycloudflare.com URL, not localhost |
| TradingView "Webhook URL is invalid" | URL must be publicly reachable — start cloudflared first |
| `trycloudflare.com` URL stops working | Quick Tunnels expire on restart. Run `cloudflared tunnel --url http://localhost:5000` again and update the alert |
| TradingView allowlist | TradingView posts from a small set of IPs. If you switch to a self-hosted reverse proxy later, allowlist `52.89.214.238`, `34.212.75.30`, `54.218.53.128`, `52.32.178.7` |
| Empty `payload` | Make sure the alert Message is actual JSON, not the default "Alert {{exchange}}:{{ticker}}" text |
