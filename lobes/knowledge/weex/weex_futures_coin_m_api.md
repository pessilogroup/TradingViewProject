# WEEX Coin-Margin Contract API

Coin-Margin contracts on WEEX settle in the underlying crypto asset and use the suffix `_DMCBL` for symbol identification.

## Margining in Underlying Assets

Unlike USDT-Margin contracts, Coin-Margin contracts are collateralized and settled in the base cryptocurrency:
*   For the `BTCUSD_DMCBL` pair, the margin asset, profit, and loss are denominated in `BTC`.
*   For the `ETHUSD_DMCBL` pair, the margin asset, profit, and loss are denominated in `ETH`.

## Sizing and Multipliers

Order sizes for Coin-Margin contracts are specified in number of contracts. Each contract has a multiplier value (e.g. 1 contract = 100 USD value for BTC, or 10 USD value for ETH).
*   **Multiplier Example**:
    *   `BTCUSD_DMCBL`: 100 USD per contract.
    *   `ETHUSD_DMCBL`: 10 USD per contract.

## Coin-Margin Endpoints

### 1. Place Coin-Margin Order
*   **Endpoint**: POST `/api/v2/mix/order/placeOrder`
*   **Parameters**:
    *   `symbol` (string, required): Suffix `_DMCBL` (e.g. `BTCUSD_DMCBL`).
    *   `marginCoin` (string, required): The underlying asset name (e.g. `BTC`, `ETH`).
    *   `side` (string, required): `open_long`, `open_short`, `close_long`, `close_short`.
    *   `orderType` (string, required): `limit` or `market`.
    *   `size` (string, required): Number of contracts.
    *   `price` (string, required for limit orders): Price.

**Request Payload Example**:
```json
{
  "symbol": "BTCUSD_DMCBL",
  "marginCoin": "BTC",
  "side": "open_long",
  "orderType": "limit",
  "price": "61000.00",
  "size": "5"
}
```

### 2. Position Info
*   **Endpoint**: GET `/api/v2/mix/position/singlePosition`
*   **Parameters**:
    *   `symbol` (string, required): e.g. `BTCUSD_DMCBL`.
    *   `marginCoin` (string, required): `BTC`.
