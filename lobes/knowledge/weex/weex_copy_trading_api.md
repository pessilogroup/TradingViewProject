# WEEX Copy Trading API

Copy trading allows professional traders to share their strategies and followers to mirror those trades automatically.

## Trader Endpoints

Professional traders can manage their copy-traded orders via the following endpoints:

### 1. Get Trader Current Orders
*   **Endpoint**: GET `/api/v1/copy/trader/currentOrder`
*   **Parameters**:
    *   `symbol` (string, optional): e.g. `BTCUSDT_UMCBL`.
    *   `page` (integer, optional): Default 1.
    *   `pageSize` (integer, optional): Default 20.

### 2. Get Trader History Orders
*   **Endpoint**: GET `/api/v1/copy/trader/historyOrder`
*   **Parameters**:
    *   `symbol` (string, optional).
    *   `startTime` (long, optional).
    *   `endTime` (long, optional).

### 3. Close Copy Trading Order
*   **Endpoint**: POST `/api/v1/copy/trader/closeOrder`
*   **Parameters**:
    *   `symbol` (string, required).
    *   `orderId` (string, required).

## Follower Endpoints

Followers can check configurations and positions using the following endpoints:

### 1. Get Follower Settings
*   **Endpoint**: GET `/api/v1/copy/follower/settings`
*   **Parameters**:
    *   `traderId` (string, required): The ID of the trader being followed.

### 2. Update Follower Settings
*   **Endpoint**: POST `/api/v1/copy/follower/updateSettings`
*   **Parameters**:
    *   `traderId` (string, required).
    *   `copyType` (integer, required): `0` for fixed amount, `1` for proportional multiplier.
    *   `copyVal` (string, required): The margin value or multiplier coefficient.

### 3. Get Follower Positions
*   **Endpoint**: GET `/api/v1/copy/follower/positions`
*   **Parameters**:
    *   `traderId` (string, optional).
    *   `symbol` (string, optional).

### 4. Get Followed Traders
*   **Endpoint**: GET `/api/v1/copy/follower/traders`
*   **Parameters**:
    *   `status` (integer, optional): `1` active, `0` paused.
