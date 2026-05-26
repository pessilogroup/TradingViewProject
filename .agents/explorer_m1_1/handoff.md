# Handoff Report - Exchange Adapters Dynamic Symbol Discovery Investigation

## 1. Observation

Direct observations made in the workspace files:

- **Weex Adapter** (`nerves/workers/trading/exchanges/weex_adapter.py`):
  - Line 29: Base URL is `self.TESTNET_URL if testnet else self.MAINNET_URL`, mapping to `https://api-demo.weex.com` or `https://api.weex.com`.
  - Lines 150-156: `get_symbol_info` makes a `GET` request to `/api/v2/contract/public/symbols`:
    ```python
    async def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        if self.dry_run:
            return {"symbol": symbol, "status": "Trading"}
            
        # Weex Contract V2 symbol info
        data = await self._request("GET", "/api/v2/contract/public/symbols", {"symbol": symbol})
        return data.get("data", {})
    ```
  - Lines 270-271: Suffix normalisation for `_UMCBL` exists:
    ```python
    if not symbol_clean.endswith("_UMCBL"):
        symbol_clean += "_UMCBL"
    ```

- **Binance Adapter & Client** (`nerves/workers/trading/exchanges/binance_adapter.py` and `nerves/workers/trading/binance_client.py`):
  - `BinanceAdapter` wraps `BinanceClient`.
  - `BinanceClient` defines `base_url` as Spot endpoints (`https://testnet.binance.vision` or `https://api.binance.com`).
  - Lines 103-121 in `binance_client.py` show `get_symbol_info` calling `/api/v3/exchangeInfo`:
    ```python
    async def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        ...
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/api/v3/exchangeInfo"
            async with session.get(url, params={"symbol": symbol}) as resp:
                data = await resp.json()
                symbols = data.get("symbols", [])
                if symbols:
                    return symbols[0]
                raise Exception(f"Symbol {symbol} not found on Binance")
    ```
  - For linear futures (USDⓈ-M Futures), the standard Binance endpoint is `GET /fapi/v1/exchangeInfo` on base URL `https://fapi.binance.com` or `https://testnet.binancefuture.com`.

- **Bybit Adapter** (`nerves/workers/trading/exchanges/bybit_adapter.py`):
  - Lines 123-128: `get_symbol_info` calls `/v5/market/instruments-info` with hardcoded `category: "spot"`:
    ```python
    async def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        if self.dry_run:
            return {"symbol": symbol, "status": "Trading"}
            
        data = await self._request("GET", "/v5/market/instruments-info", {"category": "spot", "symbol": symbol})
        return data.get("result", {}).get("list", [{}])[0]
    ```

- **Unified Interface / Protocol** (`nerves/workers/trading/exchanges/base.py`):
  - Lines 97-153 show that the `ExchangeAdapter` protocol defines no method to query active symbols or retrieve all symbols. It only has `get_symbol_info(self, symbol: str)`.

---

## 2. Logic Chain

1. **Listing Active Linear Symbols Requirements**:
   - We need to fetch all active USDT-M (linear) futures contract pairs.
   - For Weex: USDT-M futures contract symbols end with the suffix `_UMCBL` (per `lobes/knowledge/weex/weex_contract_v2_api.md`).
   - For Bybit: Instruments must be retrieved under category `linear`.
   - For Binance: Instruments should be retrieved either under Spot `/api/v3/exchangeInfo` (if Spot is simulated/used) or USDⓈ-M Futures `/fapi/v1/exchangeInfo` (if real linear futures are traded).

2. **Limitations of `get_symbol_info`**:
   - `get_symbol_info` requires a specific `symbol` query parameter.
   - `get_symbol_info` in `BybitAdapter` is hardcoded to query `category="spot"`.
   - Performing lookup in a loop for all possible symbols would cause high latency and risk rate limits.
   - Thus, `get_symbol_info` **cannot** be used to retrieve the list of active symbols dynamically.

3. **Defining a Unified Interface**:
   - Since no unified function exists in `ExchangeAdapter` to query active symbols, we must add a new method signature to the `ExchangeAdapter` protocol:
     ```python
     async def get_active_linear_symbols(self) -> List[str]:
         """Retrieve list of active linear trading symbols (e.g. USDT perps/spot)."""
         ...
     ```
   - Each adapter will implement this method according to the specific exchange's REST API details.

---

## 3. Caveats

- **Binance Spot vs Futures**: The current `BinanceClient` and `BinanceAdapter` are configured for Spot trading. If the user expects USDⓈ-M Futures (linear contracts) for Binance as well, the `BinanceClient` base URL needs to support the futures subdomain (`fapi.binance.com`), and the endpoint must use `/fapi/v1/exchangeInfo`.
- **API Status Fields**: Status field values and formatting might differ across exchanges. In the proposed implementation:
  - Weex status is assumed to be `"Trading"` (matching dry-run mock and standard responses).
  - Bybit status is checked against `"Trading"`.
  - Binance status is checked against `"TRADING"`.
- **Dry-run Behavior**: In dry-run modes, the adapters should return a curated, representative list of active symbols (e.g., `["BTCUSDT", "ETHUSDT", "SOLUSDT"]` for Binance/Bybit, and `["BTCUSDT_UMCBL", "ETHUSDT_UMCBL", "SOLUSDT_UMCBL"]` for Weex) rather than attempting real network calls.

---

## 4. Conclusion

To implement dynamic symbol discovery for active linear contract pairs across the three exchanges, we must:
1. Define a new unified method `async def get_active_linear_symbols(self) -> List[str]:` in the `ExchangeAdapter` protocol.
2. Implement `get_active_linear_symbols` in each adapter using the following endpoints and parameters:
   - **Weex**: `GET /api/v2/contract/public/symbols` (no params). Filter for symbol suffix `_UMCBL` and status `"Trading"`.
   - **Bybit**: `GET /v5/market/instruments-info` with query parameter `{"category": "linear"}`. Filter for status `"Trading"`.
   - **Binance**: `GET /api/v3/exchangeInfo` (Spot) or `GET /fapi/v1/exchangeInfo` (Futures). Filter for status `"TRADING"` and quote asset `"USDT"`.

---

## 5. Verification Method

To verify the dynamic discovery logic independently once implemented:
1. **Mock Tests (Unit Tests)**:
   - Create unit tests mock responses for each of the target endpoints.
   - Run `pytest nerves/workers/trading/tests/unit/` to verify that `get_active_linear_symbols` returns the parsed symbol list correctly.
2. **Integration Test / Trial Script**:
   - Run an integration command/script (similar to `nerves/workers/trading/scripts/test_weex_trial.py`) to hit the endpoints on the respective testnet/mainnet with real network requests (when `dry_run=False`).
   - Validate that Weex returns symbols matching `*_UMCBL`, Bybit returns linear instruments (e.g., `BTCUSDT`, `ETHUSDT`), and Binance returns USDT pairs.
