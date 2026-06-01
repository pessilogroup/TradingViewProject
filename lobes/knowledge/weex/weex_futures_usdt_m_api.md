# WEEX USDT-Margin Contract API (V2 & V3)

USDT-Margin contracts on WEEX settle in USDT and use the suffix `_UMCBL` for symbol identification.

## Symbol Naming Convention

All USDT-Margin symbols are appended with `_UMCBL`.
*   Example: `BTCUSDT_UMCBL` (Bitcoin/USDT contract), `ETHUSDT_UMCBL` (Ethereum/USDT contract).

## USDT-Margin Endpoints

### 1. Place Futures Order
*   **V2 Endpoint**: POST `/api/v2/mix/order/placeOrder`
*   **V3 Endpoint**: POST `/api/v3/mix/order/placeOrder`
*   **Parameters**:
    *   `symbol` (string, required): The symbol code (e.g. `BTCUSDT_UMCBL`).
    *   `marginCoin` (string, required): Always `USDT` for USDT-Margin contracts.
    *   `side` (string, required): `open_long`, `open_short`, `close_long`, `close_short`.
    *   `orderType` (string, required): `limit` or `market`.
    *   `size` (string, required): Order quantity in contract size.
    *   `price` (string, required for limit orders): Execution price.
    *   `presetTakeProfitPrice` (string, optional): TP price.
    *   `presetStopLossPrice` (string, optional): SL price.

**Request Payload Example**:
```json
{
  "symbol": "BTCUSDT_UMCBL",
  "marginCoin": "USDT",
  "side": "open_long",
  "orderType": "limit",
  "price": "61000.00",
  "size": "1",
  "presetTakeProfitPrice": "63000.00",
  "presetStopLossPrice": "60000.00"
}
```

### 2. OCO (One-Cancels-the-Other) Exit Orders
WEEX supports attaching target profit and stop loss parameters directly during order placement, or placing secondary exit orders:
*   **Endpoint**: POST `/api/v2/mix/order/placePlanOrder`
*   **Parameters**:
    *   `triggerPrice` (string, required): Trigger threshold price.
    *   `triggerType` (string, required): `fill_price`, `market_price`.
    *   `executePrice` (string, optional): Market trigger if empty, or limit price.

### 3. Position Information
*   **V2 Endpoint**: GET `/api/v2/mix/position/singlePosition`
*   **Parameters**:
    *   `symbol` (string, required): e.g., `BTCUSDT_UMCBL`.
    *   `marginCoin` (string, required): `USDT`.
