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

---

## 3. WEEX Spot V3 API (BETA)

### 3.1 Spot V3 Configuration
*   **Production REST API Base URL**: `https://api-spot.weex.com`
*   **Base Path**: `/api/v3`
*   **Success Response**: Successful operations return standard JSON responses with the requested payload directly, or wrapped with error/status codes depending on the endpoint status.

### 3.2 Spot V3 Endpoints Reference

#### 3.2.1 Place Order (TRADE)
Places a new limit or market order on the Spot Exchange.
*   **Path**: `POST /api/v3/order`
*   **Authentication**: Required
*   **Weights**: IP: 2, UID: 5

##### Request Parameters
| Parameter | Type | Required | Description | Allowed Values / Examples |
| :--- | :--- | :--- | :--- | :--- |
| `symbol` | String | Yes | Trading pair | e.g. `BTCUSDT` |
| `side` | String | Yes | Order side | `BUY`, `SELL` |
| `type` | String | Yes | Order type | `LIMIT`, `MARKET` |
| `timeInForce` | String | Conditional | Required when `type = LIMIT` | `GTC`, `IOC`, `FOK` |
| `quantity` | String | Yes | Order quantity | e.g. `1` |
| `price` | String | Conditional | Limit price. Required when `type = LIMIT` | e.g. `68900` |
| `newClientOrderId` | String | No | Custom tracking ID | e.g. `my-order-001` |

##### Response Model (Success)
```json
{
  "symbol": "BTCUSDT",
  "orderId": 702345678901234567,
  "clientOrderId": "my-spot-order-001",
  "transactTime": 1764506000456
}
```

#### 3.2.2 Batch Place Orders (TRADE)
Places up to 10 orders in a single request.
*   **Path**: `POST /api/v3/order/batch`
*   **Authentication**: Required
*   **Weights**: IP: 10, UID: 50

##### Request Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | String | Yes | Trading pair |
| `orderList` | Array<Object> | Yes | Up to 10 order definitions (side, type, timeInForce, quantity, price, newClientOrderId) |

##### Response Model (Success)
```json
{
  "orderList": [
    {
      "symbol": "BTCUSDT",
      "orderId": 702345678901234700,
      "clientOrderId": "batch-1",
      "transactTime": 1764506000456
    },
    {
      "symbol": "BTCUSDT",
      "clientOrderId": "batch-2",
      "errorCode": "INSUFFICIENT_BALANCE",
      "errorMsg": "insufficient balance"
    }
  ]
}
```

#### 3.2.3 Cancel Order (TRADE)
Cancels an active pending Spot order.
*   **Path**: `DELETE /api/v3/order`
*   **Authentication**: Required
*   **Weights**: IP: 1, UID: 1

##### Query Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | String | Yes | Trading pair |
| `orderId` | Long | Conditional | Required if `origClientOrderId` is empty |
| `origClientOrderId` | String | Conditional | Required if `orderId` is empty |

##### Response Model (Success)
```json
{
  "orderId": 702345678901234567,
  "status": "CANCELED"
}
```

#### 3.2.4 Cancel All Open Orders by Symbol (TRADE)
Cancels all active open orders for a specific symbol.
*   **Path**: `DELETE /api/v3/openOrders`
*   **Authentication**: Required
*   **Weights**: IP: 1, UID: 1

##### Query Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | String | Yes | Trading pair whose open orders should be cancelled |

##### Response Model (Success)
```json
[
  {
    "orderId": 702345678901234567,
    "status": "CANCELED"
  }
]
```

#### 3.2.5 Batch Cancel Orders (TRADE)
Cancels up to 10 orders in a single request.
*   **Path**: `DELETE /api/v3/order/batch`
*   **Authentication**: Required
*   **Weights**: IP: 5, UID: 10

##### Request Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | String | Yes | Trading pair |
| `orderIds` | Array<Long> | Conditional | Up to 10 order IDs. Required if `origClientOrderIds` is empty |
| `origClientOrderIds` | Array<String> | Conditional | Up to 10 client order IDs. Required if `orderIds` is empty |

##### Response Model (Success)
```json
{
  "orderList": [
    {
      "orderId": 702345678901234567,
      "status": "CANCELED"
    },
    {
      "orderId": 702345678901234568,
      "status": "EXPIRED",
      "errorMsg": "order not found"
    }
  ]
}
```

#### 3.2.6 Get Order Details (USER_DATA)
Retrieves details of a specific Spot order.
*   **Path**: `GET /api/v3/order`
*   **Authentication**: Required
*   **Weights**: IP: 2, UID: 2

##### Query Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | String | Yes | Trading pair |
| `orderId` | Long | Conditional | Required if `origClientOrderId` is empty |
| `origClientOrderId` | String | Conditional | Required if `orderId` is empty |

##### Response Model (Success)
```json
{
  "symbol": "BTCUSDT",
  "orderId": 702345678901234567,
  "clientOrderId": "my-spot-order-001",
  "price": "68900",
  "origQty": "0.01",
  "executedQty": "0.01",
  "cummulativeQuoteQty": "689.00",
  "status": "FILLED",
  "timeInForce": "GTC",
  "type": "LIMIT",
  "side": "BUY",
  "time": 1764506000456,
  "updateTime": 1764506001556,
  "isWorking": false
}
```

#### 3.2.7 Get Current Open Orders (USER_DATA)
Retrieves all open orders for a trading pair, or all pairs.
*   **Path**: `GET /api/v3/openOrders`
*   **Authentication**: Required
*   **Weights**: IP: 3, UID: 3

##### Query Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | String | No | Filter by trading pair. Returns all if omitted |

##### Response Model (Success)
```json
[
  {
    "symbol": "BTCUSDT",
    "orderId": 702345678901234567,
    "clientOrderId": "my-spot-order-001",
    "price": "68900",
    "origQty": "0.01",
    "executedQty": "0",
    "cummulativeQuoteQty": "0",
    "status": "NEW",
    "timeInForce": "GTC",
    "type": "LIMIT",
    "side": "BUY",
    "time": 1764506000456,
    "updateTime": 1764506000456,
    "isWorking": true
  }
]
```

#### 3.2.8 Get All Orders (USER_DATA)
Retrieves order history for a trading pair.
*   **Path**: `GET /api/v3/allOrders`
*   **Authentication**: Required
*   **Weights**: IP: 10, UID: 10

##### Query Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | String | Yes | Trading pair |
| `startTime` | Long | No | Start time in ms |
| `endTime` | Long | No | End time in ms (must be >= startTime) |
| `limit` | Integer | No | Page size: default 100, max 1000 |
| `page` | Integer | No | Page number: default 1 |

##### Response Model (Success)
Returns an array of order details objects (similar to Section 3.2.6).

#### 3.2.9 Get Trade History (USER_DATA)
Retrieves transaction fills details.
*   **Path**: `GET /api/v3/myTrades`
*   **Authentication**: Required
*   **Weights**: IP: 5, UID: 5

##### Query Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | String | Yes | Trading pair |
| `orderId` | Long | No | Filter by order ID |
| `startTime` | Long | No | Start time in ms |
| `endTime` | Long | No | End time in ms (must be >= startTime) |
| `limit` | Integer | No | Page size: default 100 |

##### Response Model (Success)
```json
[
  {
    "symbol": "BTCUSDT",
    "id": 801234567890123456,
    "orderId": 702345678901234567,
    "price": "68950.00",
    "qty": "0.01",
    "quoteQty": "689.50",
    "commission": "0.138",
    "time": 1764506001556,
    "isBuyer": true
  }
]
```
