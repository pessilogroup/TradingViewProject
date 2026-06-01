# WEEX Contract V2 API Technical Reference

## 1. Contract V2 API Configuration

### 1.1 Base URL
*   **Production REST API Base URL**: `https://api.weex.com`
*   **Base Path**: `/api/v2/contract`

### 1.2 Symbol Suffix
The Contract V2 API targets the USDT-M (USDT Margin) Linear Futures. All symbols in the Contract V2 API use the suffix `_UMCBL`.
*   **Example**: `BTCUSDT` becomes `BTCUSDT_UMCBL`.

---

## 2. Endpoints Reference

### 2.1 Place Contract Order
Places a new limit or market order for USDT-M linear futures.

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

#### Request Parameters Table
| Parameter | Type | Required | Description | Allowed Values / Examples |
| :--- | :--- | :--- | :--- | :--- |
| `symbol` | String | Yes | Futures symbol | e.g. `BTCUSDT_UMCBL` |
| `marginCoin` | String | Yes | Margin asset coin | e.g. `USDT` |
| `side` | String | Yes | Position side action | `open_long`, `open_short`, `close_long`, `close_short` |
| `orderType` | String | Yes | Execution type | `limit`, `market` |
| `price` | String | Yes (for Limit) | Limit execution price | e.g. `27500.50` |
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

---

### 2.2 Cancel Contract Order
Cancels an active pending contract order.

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

---

### 2.3 Get Contract Order Info
Retrieves details of a specific contract order.

*   **Path**: `GET /api/v2/contract/trade/order_info`
*   **Authentication**: Required

#### Query Parameters
| Parameter | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `symbol` | String | Yes | Futures symbol | `BTCUSDT_UMCBL` |
| `orderId` | String | Yes | System-generated Order ID | `9988776655443322` |

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

---

### 2.4 Get Position Details
Retrieves active contract position details for a specific trading pair and margin coin.

*   **Path**: `GET /api/v2/contract/position/single_position`
*   **Authentication**: Required

#### Query Parameters
| Parameter | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `symbol` | String | Yes | Futures symbol | `BTCUSDT_UMCBL` |
| `marginCoin` | String | Yes | Margin asset coin | `USDT` |

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

---

## 3. Contract V2 Migration Changelog

*   **Base URL Refactor**: Endpoint structure transitioned from `/api/v1/mix/*` (V1) to `/api/v2/contract/*` (V2).
*   **Margin Configuration**: Introduced explicit `marginCoin` specifications to separate Multi-Asset margin accounts from Single-Asset linear margin accounts.
*   **Quantity Units**: Order size parameter name changed from `qty` to `size` to standardize contract unit definitions.
*   **Client Order Tracking**: Request client tracking parameter standardized to `clientOid` in Contract V2.

---

## 4. Futures V2 /capi/v2 Endpoints Reference

### 4.1 Configuration
*   **Production REST Base URL**: `https://api-contract.weex.com`
*   **Base Path**: `/capi/v2`

### 4.2 Endpoints Details

#### 4.2.1 Place Order
Places a new limit or market futures order.
*   **Path**: `POST /capi/v2/order/placeOrder`
*   **Authentication**: Required
*   **Weights**: IP: 2, UID: 5

##### Request Body Schema
```json
{
  "symbol": "BTCUSDT_UMCBL",
  "client_oid": "order12345",
  "size": "0.01",
  "type": "1",
  "order_type": "0",
  "match_price": "0",
  "price": "68900",
  "marginMode": 1
}
```

##### Request Parameters Table
| Parameter | Type | Required | Description | Allowed Values |
| :--- | :--- | :--- | :--- | :--- |
| `symbol` | String | Yes | Futures symbol | e.g. `BTCUSDT_UMCBL` |
| `client_oid` | String | Yes | Custom order ID (<= 40 chars) | |
| `size` | String | Yes | Amount in base coin | |
| `type` | String | Yes | Execution type and side | `1`: Open long, `2`: Open short, `3`: Close long, `4`: Close short |
| `order_type` | String | Yes | Order category | `0`: Normal, `1`: Post-Only, `2`: FOK, `3`: IOC |
| `match_price` | String | Yes | Execution matching | `0`: Limit price, `1`: Market price |
| `price` | String | Yes | Price (required for limit orders) | |
| `presetTakeProfitPrice` | BigDecimal | No | Preset take-profit price | |
| `presetStopLossPrice` | BigDecimal | No | Preset stop-loss price | |
| `marginMode` | Integer | No | Margin Mode | `1`: Cross (default), `3`: Isolated |

##### Response Model (Success)
```json
{
  "client_oid": null,
  "order_id": "596471064624628269"
}
```

#### 4.2.2 Batch Orders
Places up to 20 orders in a single request.
*   **Path**: `POST /capi/v2/order/batchOrders`
*   **Authentication**: Required
*   **Weights**: IP: 5, UID: 10

##### Request Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | String | Yes | Trading pair |
| `marginMode` | Integer | No | `1`: Cross Mode, `3`: Isolated Mode |
| `orderDataList` | List | Yes | Up to 20 order objects (structure matches Place Order) |

##### Response Model (Success)
```json
{
  "order_info": [
    {
      "order_id": "596476148997685805",
      "client_oid": "order12346",
      "result": true,
      "error_code": "",
      "error_message": ""
    }
  ],
  "result": true
}
```

#### 4.2.3 Cancel Order
Cancels an active pending order.
*   **Path**: `POST /capi/v2/order/cancel_order`
*   **Authentication**: Required
*   **Weights**: IP: 2, UID: 3

##### Request Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `orderId` | String | No | System order ID. Required if `clientOid` is empty |
| `clientOid` | String | No | Client custom ID. Required if `orderId` is empty |

##### Response Model (Success)
```json
{
  "order_id": "596476148997685805",
  "client_oid": null,
  "result": true,
  "err_msg": null
}
```

#### 4.2.4 Batch Cancel Orders
Cancels up to 10 orders in a single request.
*   **Path**: `POST /capi/v2/order/cancel_batch_orders`
*   **Authentication**: Required
*   **Weights**: IP: 5, UID: 10

##### Request Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `ids` | String[] | No | List of order IDs. Required if `cids` is empty |
| `cids` | String[] | No | List of client IDs. Required if `ids` is empty |

##### Response Model (Success)
```json
{
  "result": true,
  "orderIds": ["596471064624628269"],
  "clientOids": [],
  "cancelOrderResultList": [
    {
      "err_msg": "",
      "order_id": "596471064624628269",
      "client_oid": "",
      "result": true
    }
  ],
  "failInfos": []
}
```

#### 4.2.5 Get Order Info
*   **Path**: `GET /capi/v2/order/detail`
*   **Authentication**: Required
*   **Weights**: IP: 2, UID: 2

##### Query Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `orderId` | String | Yes | System order ID |

##### Response Model (Success)
```json
{
  "symbol": "cmt_btcusdt",
  "size": "0.010000",
  "client_oid": "1763604184027_122",
  "createTime": "1763708511502",
  "filled_qty": "0.010000",
  "fee": "0.51357900",
  "order_id": "686643264626885530",
  "price": "0.0",
  "price_avg": "85596.5",
  "status": "filled",
  "type": "open_long",
  "order_type": "ioc",
  "totalProfits": "0",
  "contracts": 10000,
  "filledQtyContracts": 10000,
  "presetTakeProfitPrice": "100000.0",
  "presetStopLossPrice": "10000.0"
}
```
*Note: `status` values include `pending`, `open`, `filled`, `canceling`, `canceled`, `untriggered`. `type` values include `open_long`, `open_short`, `close_long`, `close_short`.*

#### 4.2.6 Get Current Orders
*   **Path**: `GET /capi/v2/order/current`
*   **Authentication**: Required
*   **Weights**: IP: 2, UID: 2

##### Query Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | String | No | Trading pair |
| `orderId` | Long | No | System order ID |
| `startTime` | Long | No | Start timestamp |
| `endTime` | Long | No | End timestamp |
| `limit` | Integer | No | Default 100, max 100 |
| `page` | Integer | No | Default 0 |

##### Response Model (Success)
Array of order info objects (similar to Section 4.2.5).

#### 4.2.7 Get History Orders
*   **Path**: `GET /capi/v2/order/history`
*   **Authentication**: Required
*   **Weights**: IP: 10, UID: 10

##### Query Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | String | No | Filter by trading pair |
| `pageSize` | Integer | No | Items per page |
| `createDate` | Long | No | Start timestamp in ms (<= 90 days from query date) |
| `endCreateDate` | Long | No | End timestamp in ms |

##### Response Model (Success)
Array of order info objects (similar to Section 4.2.5).

#### 4.2.8 Get Fills (Trade History)
*   **Path**: `GET /capi/v2/order/fills`
*   **Authentication**: Required
*   **Weights**: IP: 5, UID: 5

##### Query Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | String | No | Trading pair |
| `orderId` | Long | No | Order ID |
| `startTime` | Long | No | Start timestamp |
| `endTime` | Long | No | End timestamp |
| `limit` | Long | No | Default 100, max 100 |

##### Response Model (Success)
```json
{
  "list": [
    {
      "tradeId": 0,
      "orderId": 0,
      "symbol": "cmt_btcusdt",
      "marginMode": "SHARED",
      "separatedMode": "SEPARATED",
      "positionSide": "LONG",
      "orderSide": "BUY",
      "fillSize": "67",
      "fillValue": "12",
      "fillFee": "67",
      "liquidateFee": "MAKER",
      "realizePnl": "83",
      "direction": "OPEN_LONG",
      "liquidateType": "FORCE_LIQUIDATE",
      "legacyOrdeDirection": "OPEN_LONG",
      "createdTime": 1716712170527
    }
  ],
  "nextFlag": false,
  "totals": 0
}
```

#### 4.2.9 Place Trigger Order
*   **Path**: `POST /capi/v2/order/plan_order`
*   **Authentication**: Required
*   **Weights**: IP: 2, UID: 5

##### Request Parameters (Body)
| Parameter | Type | Required | Description | Allowed Values |
| :--- | :--- | :--- | :--- | :--- |
| `symbol` | String | Yes | Trading pair | e.g. `BTCUSDT_UMCBL` |
| `client_oid` | String | Yes | Custom order ID | |
| `size` | String | Yes | Order quantity (base coin) | |
| `type` | String | Yes | Direction | `1`: Open long, `2`: Open short, `3`: Close long, `4`: Close short |
| `match_type` | String | Yes | Matching | `0`: Limit price, `1`: Market price |
| `execute_price` | String | Yes | Execution price | |
| `trigger_price` | String | Yes | Trigger price | |
| `marginMode` | Integer | No | Margin Mode | `1`: Cross Mode, `3`: Isolated Mode |

##### Response Model (Success)
```json
{
  "client_oid": null,
  "order_id": "596480271352594989"
}
```

#### 4.2.10 Cancel Trigger Order
*   **Path**: `POST /capi/v2/order/cancel_plan`
*   **Authentication**: Required
*   **Weights**: IP: 2, UID: 3

##### Request Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `orderId` | String | Yes | Conditional order ID to cancel |

##### Response Model (Success)
Identical to Section 4.2.3.

#### 4.2.11 Get Current Plan Orders
*   **Path**: `GET /capi/v2/order/currentPlan`
*   **Authentication**: Required
*   **Weights**: IP: 3, UID: 3

##### Query Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | String | No | Trading pair |
| `orderId` | Long | No | Order ID filter |
| `startTime` | Long | No | Start timestamp |
| `endTime` | Long | No | End timestamp |
| `limit` | Integer | No | Default 100, max 100 |
| `page` | Integer | No | Default 0 |

##### Response Model (Success)
```json
[
  {
    "symbol": "cmt_btcusdt",
    "size": "1",
    "client_oid": "1234567890",
    "createTime": "1742213506548",
    "filled_qty": "0.5",
    "fee": "0.01",
    "order_id": "461234125",
    "price": "50000.00",
    "price_avg": "49900.00",
    "status": "1",
    "type": "1",
    "order_type": "0",
    "totalProfits": "200.00",
    "triggerPrice": "48000.00",
    "triggerPriceType": "LIMIT",
    "triggerTime": "1742213506548",
    "presetTakeProfitPrice": null,
    "presetStopLossPrice": null
  }
]
```
*Note: `status` values: `-1` (Canceled), `0` (Pending), `1` (Partially filled), `2` (Filled). `type` values: `1` (Open long) to `10` (Liquidation close short). `order_type` values: `0` (Normal), `1` (Post-only), `2` (FOK), `3` (IOC).*

#### 4.2.12 Get History Plan Orders
*   **Path**: `GET /capi/v2/order/historyPlan`
*   **Authentication**: Required
*   **Weights**: IP: 5, UID: 10

##### Query Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | String | Yes | Trading pair |
| `startTime` | Long | No | Start time |
| `endTime` | Long | No | End time |
| `delegateType` | Integer | No | Order type: `1` to `4` |
| `pageSize` | Integer | No | Items per page, default 100, max 100 |

##### Response Model (Success)
```json
{
  "list": [
    {
      "symbol": "cmt_btcusdt",
      "size": "1",
      "client_oid": "1234567890",
      "createTime": "1742213506548",
      "filled_qty": "0.5",
      "fee": "0.01",
      "order_id": "461234125",
      "price": "50000.00",
      "price_avg": "49900.00",
      "status": "1",
      "type": "1",
      "order_type": "0",
      "totalProfits": "200.00",
      "triggerPrice": "48000.00",
      "triggerPriceType": "",
      "triggerTime": "1742213506548",
      "presetTakeProfitPrice": null,
      "presetStopLossPrice": null
    }
  ],
  "nextPage": false
}
```

#### 4.2.13 Close All Positions
Closes all positions for a specific pair or all pairs at market price.
*   **Path**: `POST /capi/v2/order/closePositions`
*   **Authentication**: Required
*   **Weights**: IP: 40, UID: 50

##### Request Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | String | No | Trading pair (omit to close all) |

##### Response Model (Success)
```json
[
  {
    "positionId": 690800371848708186,
    "successOrderId": 696023766399976282,
    "errorMessage": "",
    "success": true
  }
]
```

#### 4.2.14 Cancel All Orders
Cancels all pending orders for a trading pair.
*   **Path**: `POST /capi/v2/order/cancelAllOrders`
*   **Authentication**: Required
*   **Weights**: IP: 40, UID: 50

##### Request Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `symbol` | String | No | Trading pair |
| `cancelOrderType` | String | Yes | `normal` (limit orders) or `plan` (plan orders) |

##### Response Model (Success)
```json
[
  {
    "orderId": 696026685023191898,
    "success": true
  }
]
```

#### 4.2.15 Place TP/SL Order
*   **Path**: `POST /capi/v2/order/placeTpSlOrder`
*   **Authentication**: Required
*   **Weights**: IP: 2, UID: 5

##### Request Parameters (Body)
| Parameter | Type | Required | Description | Allowed Values |
| :--- | :--- | :--- | :--- | :--- |
| `symbol` | String | Yes | Trading pair | e.g. `BTCUSDT_UMCBL` |
| `clientOrderId` | String | Yes | Custom order ID (<= 40 chars) | |
| `planType` | String | Yes | TP/SL Type | `profit_plan` or `loss_plan` |
| `triggerPrice` | String | Yes | Trigger price | |
| `executePrice` | String | No | Execution price. Omit/set to "0" for market | |
| `size` | String | Yes | Order quantity (base coin) | |
| `positionSide` | String | Yes | Position direction | `long` or `short` |
| `marginMode` | Integer | No | Margin Mode | `1`: Cross Mode, `3`: Isolated Mode |

##### Response Model (Success)
```json
[
  {
    "orderId": 696073048050107226,
    "success": true
  }
]
```

#### 4.2.16 Modify TP/SL Order
*   **Path**: `POST /capi/v2/order/modifyTpSlOrder`
*   **Authentication**: Required
*   **Weights**: IP: 2, UID: 5

##### Request Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `orderId` | Long | Yes | Order ID of the TP/SL order |
| `triggerPrice` | String | Yes | New trigger price |
| `executePrice` | String | No | New execution price. Omit/set to "0" for market |
| `triggerPriceType` | Integer | No | Trigger source: `1`: Last price (default), `3`: Mark price |

##### Response Model (Success)
```json
{
  "code": "00000",
  "msg": "success",
  "requestTime": 1765956639711,
  "data": ""
}
```
