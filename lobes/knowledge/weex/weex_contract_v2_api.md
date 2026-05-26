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
