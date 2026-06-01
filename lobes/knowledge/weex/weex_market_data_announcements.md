# WEEX Market Data and Announcements

WEEX publishes real-time specifications of supported asset lists and announcements via REST endpoints.

## Market Specification Endpoints

### 1. Spot Symbols
*   **Endpoint**: GET `/api/v1/market/symbols`
*   **Description**: Lists all supported spot trading pairs and statuses.
*   **Response Fields**:
    *   `symbol`: The name of the pair (e.g., `BTCUSDT`).
    *   `status`: `online` (trading), `offline` (suspended), or `pre_trade` (maintenance).
    *   `baseCoin`: Base cryptocurrency (e.g., `BTC`).
    *   `quoteCoin`: Quote currency (e.g., `USDT`).

### 2. Contract Configurations
*   **Endpoint**: GET `/api/v2/mix/market/contracts`
*   **Description**: Returns contract specs for all USDT-Margin and Coin-Margin pairs.
*   **Response Fields**:
    *   `symbol`: Suffix `_UMCBL` or `_DMCBL`.
    *   `pricePrecision`: Decimal precision for ordering.
    *   `minSize`: Minimum order size.
    *   `contractMultiplier`: Sizing multiplier.

## System Announcements and Updates

Updates to the API are communicated through the following channels:
*   **System Status Header**: Responses contain the `X-System-Status: normal` header. If maintenance is scheduled, this changes to `X-System-Status: maintenance`.
*   **Documentation Site**: Announced on the official WEEX developers portal.
