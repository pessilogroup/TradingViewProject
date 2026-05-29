# WEEX API Technical Reference Manual
Version: 2.1.0  
Last Updated: 2026-05-23  
Target Service: Spot and Contract V2 (USDT-M Futures)

This reference document compiles the complete, production-grade technical specifications for integrating with the WEEX exchange platform. It contains endpoint definitions, signature calculation rules, payload schemas, and WebSocket message configurations.

---

## 1. Global API Configurations

### 1.1 Base URLs

| Environment | Protocol | Base URL / Host |
| :--- | :--- | :--- |
| **Production API** | REST HTTPS | `https://api.weex.com` |
| **Production WebSocket (Spot)** | WS WSS | `wss://ws.weex.com/spot/v1/websocket` |
| **Production WebSocket (Contract)** | WS WSS | `wss://ws.weex.com/mix/v1/websocket` |
| **Demo (Sandbox) API** | REST HTTPS | `https://api-demo.weex.com` |
| **Demo (Sandbox) WebSocket** | WS WSS | `wss://ws-demo.weex.com/mix/v1/websocket` |

### 1.2 HTTP Headers
All private REST API requests must include the following headers for authentication:

*   `ACCESS-KEY`: The user's API Key.
*   `ACCESS-SIGN`: The generated HMAC-SHA256 signature (Base64-encoded).
*   `ACCESS-TIMESTAMP`: The current millisecond timestamp (e.g., `1672531199000`).
*   `ACCESS-PASSPHRASE`: The passphrase defined during API Key creation.
*   `Content-Type`: Must be `application/json`.

---

## 2. Signature Algorithm

All authenticated REST API and WebSocket login requests require a signature generated using HMAC-SHA256 with the user's API Secret Key. The signature payload is constructed as a concatenated string.

### 2.1 Signature Payload Format
The signature payload string is defined as:
```
timestamp + METHOD + requestPath + body
```
Where:
*   `timestamp`: The exact value passed in the `ACCESS-TIMESTAMP` header (e.g. `1684812345000`).
*   `METHOD`: The HTTP request method in uppercase (`GET`, `POST`, `DELETE`, etc.).
*   `requestPath`: The relative request path, including any query parameters (e.g., `/api/v1/spot/trade/order_info?symbol=BTCUSDT&orderId=1234567890`).
*   `body`: The JSON payload string for `POST` requests. For `GET` requests, or `POST` requests with no body, this must be an empty string (`""`).

### 2.2 Python Signing Example
The following code snippet demonstrates the exact procedure for generating the signature:

```python
import hmac
import hashlib
import base64
import time
import requests

def generate_weex_signature(secret_key, timestamp, method, request_path, body=""):
    # Ensure body is empty string if not provided
    payload = f"{timestamp}{method.upper()}{request_path}{body}"
    
    # Calculate HMAC-SHA256
    mac = hmac.new(
        bytes(secret_key, encoding='utf-8'),
        bytes(payload, encoding='utf-8'),
        digestmod=hashlib.sha256
    )
    
    # Base64 encode the binary digest
    signature = base64.b64encode(mac.digest()).decode('utf-8')
    return signature

# Example Usage:
# API Credentials
API_KEY = "weex_api_key_sample_123"
SECRET_KEY = "weex_secret_key_sample_456"
PASSPHRASE = "weex_passphrase_sample_789"

# Generate Timestamp
timestamp = str(int(time.time() * 1000))

# Sign a GET Request
method = "GET"
request_path = "/api/v1/spot/market/ticker?symbol=BTCUSDT"
sign = generate_weex_signature(SECRET_KEY, timestamp, method, request_path)

headers = {
    "ACCESS-KEY": API_KEY,
    "ACCESS-SIGN": sign,
    "ACCESS-TIMESTAMP": timestamp,
    "ACCESS-PASSPHRASE": PASSPHRASE,
    "Content-Type": "application/json"
}

print(f"Generated Signature: {sign}")
```

---

## 3. Spot API Reference

Success responses return HTTP 200 with a JSON body containing a `code` field. The successful code value is `"00000"`.

### 3.1 Place Spot Order
*   **Path**: `POST /api/v1/spot/trade/order`
*   **Authentication**: Required

#### Request Body Schema
```json
{
  "symbol": "BTCUSDT",
  "side": "buy",
  "type": "limit",
  "price": "27500.50",
  "quantity": "0.005",
  "clientOrderId": "cl_ord_spot_001"
}
```

| Parameter | Type | Required | Description | Values |
| :--- | :--- | :--- | :--- | :--- |
| `symbol` | String | Yes | Trading pair name | e.g. `BTCUSDT`, `ETHUSDT` |
| `side` | String | Yes | Order execution side | `buy`, `sell` |
| `type` | String | Yes | Order type | `limit`, `market` |
| `price` | String | Yes (Limit) | Price per unit | e.g. `27500.50` |
| `quantity` | String | Yes | Order size in base coin | e.g. `0.005` |
| `clientOrderId` | String | No | Custom tracking ID | e.g. `cl_ord_spot_001` |

#### Response Model (Success)
```json
{
  "code": "00000",
  "msg": "success",
  "data": {
    "orderId": "8877665544332211",
    "clientOrderId": "cl_ord_spot_001",
    "symbol": "BTCUSDT",
    "status": "new"
  }
}
```

### 3.2 Cancel Spot Order
*   **Path**: `POST /api/v1/spot/trade/cancel_order`
*   **Authentication**: Required

#### Request Body Schema
```json
{
  "symbol": "BTCUSDT",
  "orderId": "8877665544332211"
}
```

#### Response Model (Success)
```json
{
  "code": "00000",
  "msg": "success",
  "data": {
    "orderId": "8877665544332211",
    "status": "cancelled"
  }
}
```

### 3.3 Get Spot Order Details
*   **Path**: `GET /api/v1/spot/trade/order_info`
*   **Authentication**: Required

#### Query Parameters
*   `symbol` (String, Required): e.g. `BTCUSDT`
*   `orderId` (String, Required): e.g. `8877665544332211`

#### Response Model (Success)
```json
{
  "code": "00000",
  "msg": "success",
  "data": {
    "orderId": "8877665544332211",
    "clientOrderId": "cl_ord_spot_001",
    "symbol": "BTCUSDT",
    "side": "buy",
    "type": "limit",
    "price": "27500.50",
    "quantity": "0.005",
    "status": "filled",
    "filledQuantity": "0.005",
    "filledPrice": "27500.20",
    "createTime": 1684812345000
  }
}
```

---

## 4. Contract V2 API Reference

The Contract V2 API targets the USDT-M (USDT Margin) Linear Futures. Symbols in the Contract V2 API use the suffix `_UMCBL` (e.g. `BTCUSDT_UMCBL`).

### 4.1 Place Contract Order
*   **Path**: `POST /api/v2/contract/trade/order`
*   **Authentication**: Required

#### Request Body Schema
```json
{
  "symbol": "BTCUSDT_UMCBL",
  "marginCoin": "USDT",
  "side": "open_long",
  "orderType": "limit",
  "price": "27500.50",
  "size": "2",
  "clientOid": "cl_ord_cnt_001"
}
```

| Parameter | Type | Required | Description | Values |
| :--- | :--- | :--- | :--- | :--- |
| `symbol` | String | Yes | Futures symbol | e.g. `BTCUSDT_UMCBL` |
| `marginCoin` | String | Yes | Margin asset coin | e.g. `USDT` |
| `side` | String | Yes | Position side action | `open_long`, `open_short`, `close_long`, `close_short` |
| `orderType` | String | Yes | Execution type | `limit`, `market` |
| `price` | String | Yes (Limit) | Limit execution price | e.g. `27500.50` |
| `size` | String | Yes | Size of order in contract sheets | e.g. `2` |
| `clientOid` | String | No | Custom tracking ID | e.g. `cl_ord_cnt_001` |

#### Response Model (Success)
```json
{
  "code": "00000",
  "msg": "success",
  "data": {
    "orderId": "9988776655443322",
    "clientOid": "cl_ord_cnt_001",
    "symbol": "BTCUSDT_UMCBL"
  }
}
```

### 4.2 Cancel Contract Order
*   **Path**: `POST /api/v2/contract/trade/cancel_order`
*   **Authentication**: Required

#### Request Body Schema
```json
{
  "symbol": "BTCUSDT_UMCBL",
  "orderId": "9988776655443322"
}
```

#### Response Model (Success)
```json
{
  "code": "00000",
  "msg": "success",
  "data": {
    "orderId": "9988776655443322",
    "status": "cancelled"
  }
}
```

### 4.3 Get Contract Order Info
*   **Path**: `GET /api/v2/contract/trade/order_info`
*   **Authentication**: Required

#### Query Parameters
*   `symbol` (String, Required): e.g. `BTCUSDT_UMCBL`
*   `orderId` (String, Required): e.g. `9988776655443322`

#### Response Model (Success)
```json
{
  "code": "00000",
  "msg": "success",
  "data": {
    "orderId": "9988776655443322",
    "clientOid": "cl_ord_cnt_001",
    "symbol": "BTCUSDT_UMCBL",
    "marginCoin": "USDT",
    "side": "open_long",
    "orderType": "limit",
    "price": "27500.50",
    "size": "2",
    "filledSize": "2",
    "filledPrice": "27500.50",
    "fee": "-0.011",
    "status": "filled",
    "createTime": 1684812348000
  }
}
```

### 4.4 Get Position Details
*   **Path**: `GET /api/v2/contract/position/single_position`
*   **Authentication**: Required

#### Query Parameters
*   `symbol` (String, Required): e.g. `BTCUSDT_UMCBL`
*   `marginCoin` (String, Required): e.g. `USDT`

#### Response Model (Success)
```json
{
  "code": "00000",
  "msg": "success",
  "data": [
    {
      "symbol": "BTCUSDT_UMCBL",
      "marginCoin": "USDT",
      "positionId": "1122334455",
      "holdSide": "long",
      "total": "2",
      "available": "2",
      "openPrice": "27450.00",
      "liquidationPrice": "21000.00",
      "unrealizedPL": "0.101000",
      "leverage": "20",
      "margin": "2.745"
    }
  ]
}
```

### 4.5 Contract Changelog (V2 Migration Summary)
*   **Base URL Refactor**: Endpoint structure transitioned from `/api/v1/mix/*` (V1) to `/api/v2/contract/*` (V2).
*   **Margin Configuration**: Introduced explicit `marginCoin` specifications to separate Multi-Asset margin accounts from Single-Asset linear margin accounts.
*   **Quantity Units**: Order size parameter name changed from `qty` to `size` to standardize contract unit definitions.
*   **Client Order Tracking**: Request client tracking parameter standardized to `clientOid` in Contrast V2.

---

## 5. WebSocket API Reference

The WEEX WebSocket API publishes live market updates and private account execution events.

### 5.1 Public Channel Subscription
*   **Connection Endpoint**: `wss://ws.weex.com/mix/v1/websocket` (Contract)
*   **Action**: Subscribe to tickers

#### Subscription Payload
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

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `op` | String | Yes | WebSocket Operation (`subscribe`, `unsubscribe`) |
| `args` | Array | Yes | List of channel options to subscribe to |
| `instType` | String | Yes | Instrument type: `SP` (Spot), `MC` (Mix Contract) |
| `channel` | String | Yes | Target stream name (`ticker`, `books`, `candle`) |
| `instId` | String | Yes | Instrument Symbol (e.g. `BTCUSDT`, `BTCUSDT_UMCBL`) |

#### Ticker Event Payload (Received)
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

### 5.2 Private Channel Authentication
To receive private order notifications or wallet updates, the WebSocket connection must be authenticated using the API keys.

#### Login Authentication Payload
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

*   **WebSocket Sign String Generation**:
    The login sign string payload is constructed as:
    ```
    timestamp + "GET" + "/user/verify"
    ```
    Sign this string with HMAC-SHA256 using the Secret Key and Base64-encode it.

#### Login Response Model (Success)
```json
{
  "event": "login",
  "code": "00000",
  "msg": "success"
}
```

---

## 6. Demo Mode (Sandbox)

WEEX provides a Sandbox environment to test strategies without financial risk.

*   **Demo Base REST URL**: `https://api-demo.weex.com`
*   **Demo Base WS URL**: `wss://ws-demo.weex.com/mix/v1/websocket`
*   **Functionality Matrix**:
    *   Demo mode accounts must be activated via the WEEX user console.
    *   Demo API Keys and Passphrases must be generated within the Demo profile page (they are distinct from production credentials).
    *   Order execution, balance checks, and signature calculations follow identical schemas and formats to those documented in Section 3 and Section 4.
    *   No actual settlement of assets occurs in Demo Mode. Accounts are credited with mock paper assets (e.g., `10,000 SBTC` or `50,000 SUSDT`).
