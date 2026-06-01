# WEEX Sandbox Environment Guide

The WEEX Sandbox environment allows risk-free API integration testing before deploying logic to live markets.

## Sandbox Gateways

*   **REST Base URL**: `https://sandbox-api.weex.com`
*   **WebSocket Base URL**: `wss://sandbox-ws.weex.com`

## Credentials

Sandbox credentials can be obtained from the Developer Console under "Test Keys".
*   API keys in Sandbox operate only on mock markets.
*   Standard passphrase mechanisms are required.

## Requesting Test Assets

To populate your test account with mock assets (e.g., test USDT, test BTC), call the following endpoint:
*   **Endpoint**: POST `/api/v1/sandbox/mockAssets`
*   **Request Payload**:
```json
{
  "asset": "USDT",
  "amount": "10000.00"
}
```
*   **Response**:
```json
{
  "code": "00000",
  "msg": "success",
  "data": {
    "asset": "USDT",
    "balance": "10000.00"
  }
}
```

## Behavior Differences from Production

1.  **Slower Match Execution**: Orders in sandbox are processed via a mock match engine. Matching may take up to 200ms longer than live servers.
2.  **No Actual Execution**: Trades do not represent actual financial transactions.
3.  **Wiped Daily**: Sandbox account balances are reset back to default mock limits every 24 hours.
