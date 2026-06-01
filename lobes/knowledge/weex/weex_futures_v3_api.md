# WEEX Contract/Futures V3 API Technical Reference

## 1. Contract V3 API Configuration

### 1.1 Base URL
*   **Production REST API Base URL**: `https://api-contract.weex.com`
*   **Base Path**: `/capi/v3`

### 1.2 Symbol Suffix
The Contract V3 API targets the USDT-M (USDT Margin) Linear Futures. All symbols in the Contract V3 API use the suffix `_UMCBL`.
*   **Example**: `BTCUSDT` becomes `BTCUSDT_UMCBL`.

---

## 2. Endpoints Reference

### 2.1 Place Order (TRADE)
Places a new limit or market order for USDT-M linear futures.
*   **Path**: `POST /capi/v3/order`
*   **Authentication**: Required
*   **Weights**: IP: 2, UID: 5

#### Request Body Schema
```json
{
  "symbol": "BTCUSDT_UMCBL",
  "side": "BUY",
  "positionSide": "LONG",
  "type": "LIMIT",
  "timeInForce": "GTC",
  "quantity": "2",
  "price": "68900",
  "newClientOrderId": "my-order-0001",
  "tpTriggerPrice": "70500",
  "slTriggerPrice": "68000",
  "TpWorkingType": "CONTRACT_PRICE",
  "SlWorkingType": "CONTRACT_PRICE"
}
```

#### Request Parameters Table
| Parameter | Type | Required | Description | Allowed Values / Examples |
| :--- | :--- | :--- | :--- | :--- |
| `symbol` | String | Yes | Futures symbol | e.g. `BTCUSDT_UMCBL` |
| `side` | String | Yes | Order execution side | `BUY`, `SELL` |
| `positionSide` | String | Yes | Position direction | `LONG`, `SHORT` |
| `type` | String | Yes | Execution type | `LIMIT`, `MARKET` |
| `timeInForce` | String | Conditional | Required when `type = LIMIT` | `GTC`, `IOC`, `FOK` |
| `quantity` | String | Yes | Order quantity (> 0) | e.g. `2` |
| `price` | String | Conditional | Limit price. Required when `type = LIMIT` | e.g. `68900` |
| `newClientOrderId` | String | Yes | Custom tracking ID (1-36 chars, regex: `^[\\.A-Z\:/a-z0-9_-]{1,36}$`) | e.g. `my-order-0001` |
| `tpTriggerPrice` | String | No | Optional Take Profit trigger price | e.g. `70500` |
| `slTriggerPrice` | String | No | Optional Stop Loss trigger price | e.g. `68000` |
| `TpWorkingType` | String | No | TP trigger source | `CONTRACT_PRICE`, `MARK_PRICE`. Default `CONTRACT_PRICE` |
| `SlWorkingType` | String | No | SL trigger source | `CONTRACT_PRICE`, `MARK_PRICE`. Default `CONTRACT_PRICE` |

#### Response Model (Success)
```json
{
  "orderId": "702345678901234567",
  "clientOrderId": "my-order-0001",
  "success": true,
  "errorCode": "",
  "errorMessage": ""
}
```

---

### 2.2 Place Orders Batch (TRADE)
Places up to 5 orders in a single request.
*   **Path**: `POST /capi/v3/batchOrders`
*   **Authentication**: Required
*   **Weights**: IP: 5, UID: 10

#### Request Body Schema
```json
{
  "batchOrders": [
    {
      "symbol": "BTCUSDT_UMCBL",
      "side": "BUY",
      "positionSide": "LONG",
      "type": "LIMIT",
      "quantity": "1",
      "price": "68900",
      "newClientOrderId": "batch-order-001"
    }
  ]
}
```

#### Response Model (Success)
An array of Place Order response objects (similar to Section 2.1).

---

### 2.3 Cancel Order (TRADE)
Cancels an active pending contract order.
*   **Path**: `DELETE /capi/v3/order`
*   **Authentication**: Required
*   **Weights**: IP: 2, UID: 3

#### Query Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `orderId` | Long | Conditional | Required if `origClientOrderId` is empty |
| `origClientOrderId` | String | Conditional | Required if `orderId` is empty |

#### Response Model (Success)
```json
{
  "orderId": "702345678901234567",
  "origClientOrderId": "my-order-0001",
  "success": true,
  "errorCode": "",
  "errorMessage": ""
}
```

---

### 2.4 Cancel Orders Batch (TRADE)
Cancels up to 10 orders in a single request.
*   **Path**: `DELETE /capi/v3/batchOrders`
*   **Authentication**: Required
*   **Weights**: IP: 5, UID: 10

#### Request Parameters (Body)
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `orderIdList` | Array<Long> | Conditional | Up to 10 order IDs. Required if `origClientOrderIdList` is empty |
| `origClientOrderIdList` | Array<String> | Conditional | Up to 10 client order IDs. Required if `orderIdList` is empty |

#### Response Model (Success)
Returns a list of Cancel Order response objects (similar to Section 2.3).

---

### 2.5 Cancel All Open Orders (TRADE)
Cancels all active open orders, optionally filtered by symbol.
*   **Path**: `DELETE /capi/v3/allOpenOrders`
*   **Authentication**: Required
*   **Weights**: IP: 5, UID: 10

#### Query Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | String | No | Filter by trading pair. Omit to cancel all open orders across symbols. |

#### Response Model (Success)
```json
[
  {
    "orderId": 702345678901234567,
    "success": true,
    "errorCode": "",
    "errorMessage": ""
  }
]
```

---

### 2.6 Close Positions (TRADE)
Closes all positions or a specific symbol's positions at market price.
*   **Path**: `POST /capi/v3/closePositions`
*   **Authentication**: Required
*   **Weights**: IP: 40, UID: 50

#### Request Parameters (Body)
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | String | No | Trading pair to close. Omit to close all positions. |

#### Response Model (Success)
```json
[
  {
    "positionId": 689987235755328154,
    "success": true,
    "successOrderId": 702345678901234580,
    "errorMessage": ""
  }
]
```

---

### 2.7 Place Conditional Order (TRADE)
Places a new conditional algo order (e.g. trigger/stop orders).
*   **Path**: `POST /capi/v3/algoOrder`
*   **Authentication**: Required
*   **Weights**: IP: 2, UID: 5

#### Request Body Schema
```json
{
  "symbol": "BTCUSDT_UMCBL",
  "side": "BUY",
  "positionSide": "LONG",
  "type": "STOP",
  "quantity": "1",
  "price": "68800",
  "triggerPrice": "68900",
  "clientAlgoId": "algo-001"
}
```

#### Request Parameters Table
| Parameter | Type | Required | Description | Allowed Values |
| :--- | :--- | :--- | :--- | :--- |
| `symbol` | String | Yes | Trading pair | e.g. `BTCUSDT_UMCBL` |
| `side` | String | Yes | Order side | `BUY`, `SELL` |
| `positionSide` | String | Yes | Position side | `LONG`, `SHORT` |
| `type` | String | Yes | Conditional type | `STOP`, `TAKE_PROFIT`, `STOP_MARKET`, `TAKE_PROFIT_MARKET` |
| `quantity` | String | Yes | Quantity to execute (> 0) | e.g. `1` |
| `price` | String | Conditional | Execution price. Required for `STOP` / `TAKE_PROFIT` | e.g. `68800` |
| `triggerPrice` | String | Yes | Trigger price (> 0) | e.g. `68900` |
| `clientAlgoId` | String | Yes | Client identifier (1-36 characters) | e.g. `algo-001` |
| `presetTakeProfitPrice` | String | No | Preset TP trigger price | |
| `presetStopLossPrice` | String | No | Preset SL trigger price | |
| `TpWorkingType` | String | No | TP trigger source | `CONTRACT_PRICE`, `MARK_PRICE`. Default `CONTRACT_PRICE` |
| `SlWorkingType` | String | No | SL trigger source | `CONTRACT_PRICE`, `MARK_PRICE`. Default `CONTRACT_PRICE` |

#### Response Model (Success)
Identical to Section 2.1.

---

### 2.8 Cancel Conditional Order (TRADE)
Cancels an active conditional order.
*   **Path**: `DELETE /capi/v3/algoOrder`
*   **Authentication**: Required
*   **Weights**: IP: 2, UID: 3

#### Query Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `orderId` | Long | Yes | Conditional order ID to cancel |

#### Response Model (Success)
Identical to Section 2.3.

---

### 2.9 Cancel All Conditional Orders (TRADE)
Cancels all active conditional orders, optionally filtered by symbol.
*   **Path**: `DELETE /capi/v3/algoOpenOrders`
*   **Authentication**: Required
*   **Weights**: IP: 5, UID: 10

#### Query Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | String | No | Filter by trading pair. Omit to cancel all. |

#### Response Model (Success)
```json
[
  {
    "orderId": 712345678901234567,
    "success": true,
    "errorCode": "",
    "errorMessage": ""
  }
]
```

---

### 2.10 Place TP/SL Conditional Orders (TRADE)
Places a take-profit or stop-loss trigger order.
*   **Path**: `POST /capi/v3/placeTpSlOrder`
*   **Authentication**: Required
*   **Weights**: IP: 2, UID: 5

#### Request Body Schema
```json
{
  "symbol": "BTCUSDT_UMCBL",
  "clientAlgoId": "tpsl-001",
  "planType": "TAKE_PROFIT",
  "triggerPrice": "70500",
  "executePrice": "0",
  "quantity": "2",
  "positionSide": "LONG",
  "triggerPriceType": "CONTRACT_PRICE"
}
```

#### Request Parameters Table
| Parameter | Type | Required | Description | Allowed Values |
| :--- | :--- | :--- | :--- | :--- |
| `symbol` | String | Yes | Trading pair | e.g. `BTCUSDT_UMCBL` |
| `clientAlgoId` | String | Yes | Client identifier (1-36 chars) | e.g. `tpsl-001` |
| `planType` | String | Yes | TP/SL Plan Type | `TAKE_PROFIT`, `STOP_LOSS` |
| `triggerPrice` | String | Yes | Trigger price (> 0) | e.g. `70500` |
| `executePrice` | String | Conditional | Execution price. Omit or set to "0" for market execution | e.g. `70500` or `0` |
| `quantity` | String | Yes | Quantity to execute | e.g. `2` |
| `positionSide` | String | Yes | Position side | `LONG`, `SHORT` |
| `triggerPriceType` | String | No | Trigger source | `CONTRACT_PRICE`, `MARK_PRICE` |

#### Response Model (Success)
```json
[
  {
    "success": true,
    "orderId": 812345678901234900,
    "errorCode": "",
    "errorMessage": ""
  }
]
```

---

### 2.11 Modify TP/SL Conditional Order (TRADE)
Modifies trigger and execution prices of an active TP/SL order.
*   **Path**: `POST /capi/v3/modifyTpSlOrder`
*   **Authentication**: Required
*   **Weights**: IP: 2, UID: 5

#### Request Body Schema
```json
{
  "orderId": 812345678901234900,
  "triggerPrice": "71000",
  "executePrice": "0",
  "triggerPriceType": "MARK_PRICE"
}
```

#### Response Model (Success)
```json
{
  "success": true
}
```

---

### 2.12 Get Order Info (USER_DATA)
Retrieves details of a specific contract order.
*   **Path**: `GET /capi/v3/order`
*   **Authentication**: Required
*   **Weights**: IP: 2, UID: 3

#### Query Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `orderId` | Long | Yes | System order ID to query |

#### Response Model (Success)
```json
{
  "avgPrice": "68990.5",
  "clientOrderId": "my-order-0001",
  "cumQuote": "689.905",
  "executedQty": "0.01",
  "orderId": 702345678901234567,
  "origQty": "0.01",
  "price": "69000",
  "reduceOnly": false,
  "side": "BUY",
  "positionSide": "LONG",
  "status": "FILLED",
  "stopPrice": "0",
  "symbol": "BTCUSDT",
  "time": 1764505700123,
  "timeInForce": "GTC",
  "type": "LIMIT",
  "updateTime": 1764505701456,
  "workingType": "CONTRACT_PRICE"
}
```

---

### 2.13 Get Current Open Orders (USER_DATA)
Retrieves active open contract orders.
*   **Path**: `GET /capi/v3/openOrders`
*   **Authentication**: Required
*   **Weights**: IP: 2, UID: 3

#### Query Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | String | No | Filter by trading pair |
| `orderId` | String | No | Return orders with ID greater than this value |
| `startTime` | Long | No | Start timestamp in ms |
| `endTime` | Long | No | End timestamp in ms |
| `limit` | Integer | No | Page size: 1-100, default 100 |
| `page` | Integer | No | Page index starting from 0, default 0 |

#### Response Model (Success)
Array of objects identical to Section 2.12.

---

### 2.14 Get Order History (USER_DATA)
Retrieves historical contract orders (within 90 days).
*   **Path**: `GET /capi/v3/order/history`
*   **Authentication**: Required
*   **Weights**: IP: 10, UID: 10

#### Query Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | String | No | Filter by trading pair |
| `limit` | Integer | No | Page size: 1-1000, default 500 |
| `startTime` | Long | No | Start timestamp in ms |
| `endTime` | Long | No | End timestamp in ms (must be <= 90 days from startTime) |
| `page` | Integer | No | Page index starting from 0, default 0 |

#### Response Model (Success)
Array of objects identical to Section 2.12.

---

### 2.15 Get Trade Details / Fills (USER_DATA)
Retrieves detailed transactions/fills.
*   **Path**: `GET /capi/v3/userTrades`
*   **Authentication**: Required
*   **Weights**: IP: 5, UID: 5

#### Query Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | String | No | Filter by trading pair |
| `orderId` | Long | No | Filter by order ID |
| `startTime` | Long | No | Start timestamp in ms |
| `endTime` | Long | No | End timestamp in ms |
| `limit` | Integer | No | Page size: 1-100, default 100 |

#### Response Model (Success)
```json
[
  {
    "id": 801234567890123456,
    "orderId": 702345678901234567,
    "symbol": "BTCUSDT",
    "buyer": true,
    "commission": "0.138",
    "commissionAsset": "USDT",
    "maker": false,
    "price": "69000",
    "qty": "0.01",
    "quoteQty": "690",
    "realizedPnl": "0",
    "side": "BUY",
    "positionSide": "LONG",
    "time": 1764505701456
  }
]
```

---

### 2.16 Get Current Conditional Orders (USER_DATA)
Retrieves active open algo/conditional orders.
*   **Path**: `GET /capi/v3/openAlgoOrders`
*   **Authentication**: Required
*   **Weights**: IP: 3, UID: 3

#### Query Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | String | No | Filter by trading pair |
| `startTime` | Long | No | Start time in ms |
| `endTime` | Long | No | End time in ms (must be >= startTime) |
| `page` | Integer | No | Page number, default 1 |
| `limit` | Integer | No | Page size: 1-100, default 100 |

#### Response Model (Success)
```json
[
  {
    "algoId": 812345678901234500,
    "clientAlgoId": "algo-20240201-1",
    "algoType": "CONDITIONAL",
    "orderType": "STOP",
    "symbol": "BTCUSDT",
    "side": "BUY",
    "positionSide": "LONG",
    "timeInForce": "GTC",
    "quantity": "0.01",
    "algoStatus": "UNTRIGGERED",
    "actualOrderId": null,
    "actualPrice": "0",
    "triggerPrice": "68900",
    "price": "68800",
    "tpTriggerPrice": "70500",
    "tpPrice": "70500",
    "slTriggerPrice": "68000",
    "slPrice": "0",
    "tpOrderType": "MARK_PRICE",
    "workingType": "MARK_PRICE",
    "closePosition": false,
    "reduceOnly": false,
    "createTime": 1764505800123,
    "updateTime": 1764505800123,
    "triggerTime": 0
  }
]
```

---

### 2.17 Get Conditional Order History (USER_DATA)
Retrieves conditional order histories.
*   **Path**: `GET /capi/v3/allAlgoOrders`
*   **Authentication**: Required
*   **Weights**: IP: 5, UID: 10

#### Query Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | String | No | Filter by trading pair |
| `startTime` | Long | No | Start time in ms |
| `endTime` | Long | No | End time in ms (within 90 days of startTime) |
| `limit` | Integer | No | Page size: 1-1000, default 500 |

#### Response Model (Success)
```json
{
  "orders": [
    {
      "algoId": 812345678901234500,
      "clientAlgoId": "algo-20240201-1",
      "algoType": "PLAN",
      "orderType": "STOP",
      "symbol": "BTCUSDT",
      "side": "BUY",
      "positionSide": "LONG",
      "timeInForce": "GTC",
      "quantity": "0.01",
      "algoStatus": "TRIGGERED",
      "actualOrderId": 702345678901234700,
      "actualPrice": "68850",
      "triggerPrice": "68900",
      "price": "68800",
      "workingType": "MARK_PRICE",
      "createTime": 1764505800123,
      "updateTime": 1764506000456,
      "triggerTime": 1764506000123
    }
  ],
  "hasMore": false
}
```

---

## 3. General Limits and Constraints
1.  **Date Ranges**: The difference between query `startTime` and `endTime` cannot exceed **90 days**.
2.  **Trade History Fills Limit**: If `startTime` and `endTime` are omitted, defaults to the last 7 days. The query range cannot exceed **7 days**, and data is only retained for **365 days**.
3.  **Batch Orders Limits**:
    *   Contract V3 Batch Place: max 5 orders.
    *   Contract V3 Batch Cancel: max 10 orders.
