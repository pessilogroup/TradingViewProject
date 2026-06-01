# WEEX WebSocket API

The WEEX WebSocket API provides real-time market data updates and private account notifications.

## Connection Gateways

*   **Public Channels**: `wss://ws.weex.com/public` or `wss://ws-api.weex.com/public`
*   **Private Channels**: `wss://ws.weex.com/private` or `wss://ws-api.weex.com/private`

## Heartbeats (Ping/Pong)

To maintain the connection, clients must send a ping frame every 30 seconds.
*   **Client Ping**: `{"op": "ping"}`
*   **Server Pong**: `{"op": "pong"}`

## Public Subscription Structure

Clients subscribe to public channels by sending a JSON request:
```json
{
  "op": "subscribe",
  "args": ["ticker:BTCUSDT", "depth:BTCUSDT", "kline:1m:BTCUSDT"]
}
```

### Public Channels
1.  **Ticker**: `ticker:<symbol>` - Real-time last price, high, low, and 24h volume.
2.  **Orderbook**: `depth:<symbol>` - Top bid/ask price levels.
3.  **Trades**: `trade:<symbol>` - Recent execution reports.
4.  **Kline**: `kline:<interval>:<symbol>` - Candle chart data.

## Private Subscription Structure

Private channels require authentication before subscription.

### 1. Authentication Message
Clients must send a login frame immediately after connecting:
```json
{
  "op": "login",
  "args": [
    {
      "apiKey": "your_api_key",
      "passphrase": "your_passphrase",
      "timestamp": 1672531200000,
      "sign": "generated_signature_string"
    }
  ]
}
```

### 2. Private Subscriptions
Once logged in, subscribe to account channels:
```json
{
  "op": "subscribe",
  "args": ["order", "position", "account"]
}
```

*   `order`: Updates on spot and futures orders (new, execution, cancellation).
*   `position`: Real-time updates on active positions and margin changes.
*   `account`: Account balance and wallet changes.
