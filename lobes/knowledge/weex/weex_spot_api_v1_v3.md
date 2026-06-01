# WEEX Spot API (V1 & V3)

WEEX provides Spot API access through both V1 and V3 protocols. V3 represents the modern standard with faster matching queues and lower rates.

## Spot Endpoints

### 1. Place Spot Order
*   **V1 Endpoint**: POST `/api/v1/spot/order`
*   **V3 Endpoint**: POST `/api/v3/spot/order`
*   **Parameters**:
    *   `symbol` (string, required): Trading pair (e.g., `BTCUSDT`).
    *   `side` (string, required): `buy` or `sell`.
    *   `type` (string, required): `limit` or `market`.
    *   `quantity` (string, required): Order quantity.
    *   `price` (string, required for limit orders): Order price.
    *   `clientOid` (string, optional): Client order ID.

**Request Payload Example**:
```json
{
  "symbol": "BTCUSDT",
  "side": "buy",
  "type": "limit",
  "price": "60500.00",
  "quantity": "0.01",
  "clientOid": "cli_spot_001"
}
```

### 2. Batch Place Orders
*   **V1 Endpoint**: POST `/api/v1/spot/batch-order`
*   **Parameters**:
    *   `symbol` (string, required): Trading pair.
    *   `ordersList` (array of objects, required): Up to 10 orders. Each order contains `side`, `type`, `price`, `quantity`, `clientOid`.

### 3. Cancel Spot Order
*   **V1 Endpoint**: POST `/api/v1/spot/cancel`
*   **V3 Endpoint**: POST `/api/v3/spot/cancel`
*   **Parameters**:
    *   `symbol` (string, required): Trading pair.
    *   `orderId` (string, required unless clientOid is provided): Order ID.
    *   `clientOid` (string, optional): Client order ID.

### 4. Order Details
*   **V1 Endpoint**: GET `/api/v1/spot/order-info`
*   **Parameters**:
    *   `symbol` (string, required).
    *   `orderId` (string, required).

### 5. Trade History
*   **V1 Endpoint**: GET `/api/v1/spot/fills`
*   **Parameters**:
    *   `symbol` (string, required).
    *   `limit` (integer, optional): Default 100, max 500.
