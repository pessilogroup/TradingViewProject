# WEEX WebSocket API Technical Reference

## 1. WebSocket Base URLs

WEEX WebSocket API endpoints publish live market updates and private account execution events.

| Environment / Segment | Protocol | Host URL |
| :--- | :--- | :--- |
| **Production Spot WebSocket** | WS / WSS | `wss://ws.weex.com/spot/v1/websocket` |
| **Production Contract WebSocket** | WS / WSS | `wss://ws.weex.com/mix/v1/websocket` |
| **Demo Sandbox WebSocket** | WS / WSS | `wss://ws-demo.weex.com/mix/v1/websocket` |

---

## 2. Public Channel Subscription

### 2.1 Subscription Request Payload
Subscribes to market tickers, order book updates, or candlestick streams.

```json
{
  "op": "subscribe",
  "args": [
    {
      "instType": "MC",
      "channel": "ticker",
      "instId": "BTCUSDT_UMCBL"
    }
  ]
}
```

### 2.2 Subscription Payload Field Details
| Field | Type | Required | Description | Allowed Values |
| :--- | :--- | :--- | :--- | :--- |
| `op` | String | Yes | Operation command to perform. | `subscribe`, `unsubscribe` |
| `args` | Array | Yes | List of channel details to subscribe to. | Array of channel definitions |
| `instType` | String | Yes | Instrument type segment. | `SP` (Spot), `MC` (Mix Contract) |
| `channel` | String | Yes | Target stream data channel. | `ticker`, `books`, `candle` |
| `instId` | String | Yes | Instrument pair symbol ID. | e.g. `BTCUSDT`, `BTCUSDT_UMCBL` |

### 2.3 Received Ticker Event Payload (Example)
```json
{
  "action": "snapshot",
  "arg": {
    "instType": "MC",
    "channel": "ticker",
    "instId": "BTCUSDT_UMCBL"
  },
  "data": [
    {
      "last": "27520.50",
      "bestBid": "27520.00",
      "bestAsk": "27521.00",
      "high24h": "28100.00",
      "low24h": "27200.00",
      "volume24h": "12005.45",
      "timestamp": 1684812350000
    }
  ]
}
```

---

## 3. Private Channel Authentication

Private websocket channels publish real-time account-specific events (e.g. fills, margin updates). Connection authentication is required.

### 3.1 Login Authentication Payload
```json
{
  "op": "login",
  "args": [
    {
      "apiKey": "weex_api_key_sample_123",
      "passphrase": "weex_passphrase_sample_789",
      "timestamp": "1684812345000",
      "sign": "generated_signature_base64"
    }
  ]
}
```

### 3.2 WebSocket Signature Calculation Rules
The websocket authentication signature (`sign`) is calculated by signing a formatted string using the HMAC-SHA256 algorithm with the API Secret Key and then Base64-encoding the resulting digest.

*   **Signature String Format**:
    ```
    timestamp + "GET" + "/user/verify"
    ```
    *   `timestamp`: The current millisecond timestamp (matching the payload `timestamp` field exactly, e.g. `1684812345000`).
    *   `METHOD`: Always the literal string `GET`.
    *   `requestPath`: Always the literal string `/user/verify`.

### 3.3 Login Success Response Model
```json
{
  "event": "login",
  "code": "00000",
  "msg": "success"
}
```
