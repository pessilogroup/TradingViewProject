# WEEX Spot API Technical Reference

## 1. Spot API Configuration

### 1.1 Base URL
*   **Production REST API Base URL**: `https://api.weex.com`
*   **Base Path**: `/api/v1/spot`

### 1.2 HTTP Headers
All private REST API requests to the Spot API must include the following headers for authentication:

| Header Name | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `ACCESS-KEY` | String | Yes | The user's API Key. | `weex_api_key_sample_123` |
| `ACCESS-SIGN` | String | Yes | The generated HMAC-SHA256 signature (Base64-encoded). | `generated_signature_base64_here` |
| `ACCESS-TIMESTAMP` | String | Yes | The current millisecond timestamp. | `1684812345000` |
| `ACCESS-PASSPHRASE` | String | Yes | The passphrase defined during API Key creation. | `weex_passphrase_sample_789` |
| `Content-Type` | String | Yes | Payload type. Must be application/json. | `application/json` |

### 1.3 Success Response Code
All successful operations return HTTP 200 with a JSON response body. A success is explicitly indicated by a `code` value of `"00000"`.

---

## 2. Endpoints Reference

### 2.1 Place Spot Order
Places a new limit or market order on the Spot Exchange.

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

#### Request Parameters Table
| Parameter | Type | Required | Description | Allowed Values / Examples |
| :--- | :--- | :--- | :--- | :--- |
| `symbol` | String | Yes | Trading pair name | e.g. `BTCUSDT`, `ETHUSDT` |
| `side` | String | Yes | Order execution side | `buy`, `sell` |
| `type` | String | Yes | Order type | `limit`, `market` |
| `price` | String | Yes (for Limit) | Price per unit | e.g. `27500.50` |
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

---

### 2.2 Cancel Spot Order
Cancels an active pending Spot order.

*   **Path**: `POST /api/v1/spot/trade/cancel_order`
*   **Authentication**: Required

#### Request Body Schema
```json
{
  "symbol": "BTCUSDT",
  "orderId": "8877665544332211"
}
```

#### Request Parameters Table
| Parameter | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `symbol` | String | Yes | Trading pair name | `BTCUSDT` |
| `orderId` | String | Yes | System-generated Order ID | `8877665544332211` |

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

---

### 2.3 Get Spot Order Details
Retrieves details of a specific Spot order.

*   **Path**: `GET /api/v1/spot/trade/order_info`
*   **Authentication**: Required

#### Query Parameters
| Parameter | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `symbol` | String | Yes | Trading pair name | `BTCUSDT` |
| `orderId` | String | Yes | System-generated Order ID | `8877665544332211` |

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
