# WEEX API Reference Index

This document provides a comprehensive mapping of all WEEX REST API endpoints and WebSocket channels to their respective detailed documentation files.

## REST API Endpoint Mapping

| API Category | HTTP Method | Endpoint | Description | Markdown Reference File |
| :--- | :--- | :--- | :--- | :--- |
| **Authentication** | POST/GET | All | V2 and V3 API signing, timestamping, and authorization headers | [weex_signatures_auth.md](weex_signatures_auth.md) |
| **Spot V1** | POST | `/api/v1/spot/order` | Place a single spot order | [weex_spot_api_v1_v3.md](weex_spot_api_v1_v3.md) |
| **Spot V1** | POST | `/api/v1/spot/batch-order` | Batch place spot orders | [weex_spot_api_v1_v3.md](weex_spot_api_v1_v3.md) |
| **Spot V1** | POST | `/api/v1/spot/cancel` | Cancel an active spot order | [weex_spot_api_v1_v3.md](weex_spot_api_v1_v3.md) |
| **Spot V1** | GET | `/api/v1/spot/order-info` | Retrieve spot order details | [weex_spot_api_v1_v3.md](weex_spot_api_v1_v3.md) |
| **Spot V1** | GET | `/api/v1/spot/fills` | Retrieve spot trade execution history | [weex_spot_api_v1_v3.md](weex_spot_api_v1_v3.md) |
| **Spot V3** | POST | `/api/v3/spot/order` | Place a spot order using V3 format | [weex_spot_api_v1_v3.md](weex_spot_api_v1_v3.md) |
| **Spot V3** | POST | `/api/v3/spot/cancel` | Cancel an active spot order using V3 format | [weex_spot_api_v1_v3.md](weex_spot_api_v1_v3.md) |
| **USDT-M Futures** | POST | `/api/v2/mix/order/placeOrder` | Place USDT-Margin contract order (`_UMCBL`) | [weex_futures_usdt_m_api.md](weex_futures_usdt_m_api.md) |
| **USDT-M Futures** | POST | `/api/v2/mix/order/cancelOrder` | Cancel USDT-Margin contract order | [weex_futures_usdt_m_api.md](weex_futures_usdt_m_api.md) |
| **USDT-M Futures** | GET | `/api/v2/mix/position/singlePosition` | Get single position information for USDT-M | [weex_futures_usdt_m_api.md](weex_futures_usdt_m_api.md) |
| **USDT-M Futures** | POST | `/api/v3/mix/order/placeOrder` | Place V3 USDT-Margin contract order | [weex_futures_usdt_m_api.md](weex_futures_usdt_m_api.md) |
| **Coin-M Futures** | POST | `/api/v2/mix/order/placeOrder` | Place Coin-Margin contract order (`_DMCBL`) | [weex_futures_coin_m_api.md](weex_futures_coin_m_api.md) |
| **Coin-M Futures** | GET | `/api/v2/mix/position/singlePosition` | Get single position for Coin-M contract | [weex_futures_coin_m_api.md](weex_futures_coin_m_api.md) |
| **Copy Trading** | GET | `/api/v1/copy/trader/currentOrder` | Get copy trading active orders for trader | [weex_copy_trading_api.md](weex_copy_trading_api.md) |
| **Copy Trading** | GET | `/api/v1/copy/trader/historyOrder` | Get copy trading history orders for trader | [weex_copy_trading_api.md](weex_copy_trading_api.md) |
| **Copy Trading** | GET | `/api/v1/copy/follower/settings` | Get follower settings | [weex_copy_trading_api.md](weex_copy_trading_api.md) |
| **Copy Trading** | POST | `/api/v1/copy/follower/updateSettings`| Update follower copy trading settings | [weex_copy_trading_api.md](weex_copy_trading_api.md) |
| **Copy Trading** | GET | `/api/v1/copy/follower/positions` | Get follower active positions | [weex_copy_trading_api.md](weex_copy_trading_api.md) |
| **Copy Trading** | GET | `/api/v1/copy/follower/traders` | Get list of followed traders | [weex_copy_trading_api.md](weex_copy_trading_api.md) |
| **Market Data** | GET | `/api/v1/market/symbols` | Get supported trading pairs and statuses | [weex_market_data_announcements.md](weex_market_data_announcements.md) |
| **Market Data** | GET | `/api/v2/mix/market/contracts` | Get contract list and details | [weex_market_data_announcements.md](weex_market_data_announcements.md) |
| **Sandbox** | POST | `/api/v1/sandbox/mockAssets` | Request mock assets for testing | [weex_sandbox_guide.md](weex_sandbox_guide.md) |

## WebSocket Channel Mapping

| Channel Category | Type | Connection Endpoint | Subscription Channels | Markdown Reference File |
| :--- | :--- | :--- | :--- | :--- |
| **Public Market** | WS | `wss://ws.weex.com/public` | `ticker`, `depth`, `trade`, `kline` | [weex_websocket_channels.md](weex_websocket_channels.md) |
| **Private User** | WS | `wss://ws.weex.com/private` | `order`, `position`, `account` | [weex_websocket_channels.md](weex_websocket_channels.md) |

## Rate Limits and Weights

For API rate limit weight tables, headers, and 429 response schemas, refer to [weex_rate_limits_weights.md](weex_rate_limits_weights.md).
