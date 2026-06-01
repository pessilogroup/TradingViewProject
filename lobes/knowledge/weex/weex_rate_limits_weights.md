# WEEX API Rate Limits and Weights

WEEX API uses a combination of rate limits and endpoint weight allocations to ensure system stability.

## Rate Limit Rules

1.  **IP Rate Limit**: Max 2000 requests per minute per IP address.
2.  **API Key Rate Limit**: Max 10 requests per second (rps) per API key for order creation.
3.  **Weight Limit**: Max 1200 request weight units per minute.

## Endpoint Weighting Table

Different endpoints consume different amounts of your minute weight limit:

| HTTP Method | Endpoint | Weight Cost |
| :--- | :--- | :--- |
| **POST** | `/api/v1/spot/order` | 1 |
| **POST** | `/api/v1/spot/batch-order` | 5 |
| **POST** | `/api/v1/spot/cancel` | 1 |
| **POST** | `/api/v2/mix/order/placeOrder` | 2 |
| **GET** | `/api/v2/mix/position/singlePosition` | 2 |
| **GET** | `/api/v1/market/symbols` | 10 |
| **GET** | `/api/v1/spot/fills` | 5 |

## Rate Limit Headers

Responses include headers detailing current consumption:
*   `X-Limit-Limit`: Maximum weight allowance per minute (e.g. `1200`).
*   `X-Limit-Remaining`: Remaining weight allowance in the current window.
*   `X-Limit-Reset`: Millisecond timestamp when the current limit window resets.

## HTTP 429 Response Schema

If a rate limit is exceeded, the server returns an HTTP 429 status code with this JSON body:
```json
{
  "code": "40029",
  "msg": "Too many requests. Please try again later.",
  "data": {
    "retryAfterMs": 1500
  }
}
```
