import pytest
from unittest.mock import AsyncMock, patch
from exchanges.weex_adapter import WeexAdapter
from exchanges.base import ExchangeErrorCategory

@pytest.mark.asyncio
async def test_weex_adapter_properties():
    adapter = WeexAdapter(
        api_key="mock_key",
        api_secret="mock_secret",
        passphrase="mock_passphrase",
        testnet=True,
        dry_run=True
    )
    assert adapter.exchange_name == "weex"
    assert adapter.exchange_id == "weex"
    assert adapter.is_testnet is True
    assert adapter.is_dry_run is True
    assert "MARKET" in adapter.supported_order_types

def test_weex_signature_generation():
    adapter = WeexAdapter(
        api_key="mock_key",
        api_secret="mock_secret",
        passphrase="mock_passphrase",
        testnet=True,
        dry_run=True
    )
    timestamp = "1684812345000"
    method = "POST"
    request_path = "/api/v2/contract/trade/order"
    body = '{"symbol":"BTCUSDT_UMCBL"}'
    
    headers = adapter._sign_request(method, request_path, body)
        
    assert headers["ACCESS-KEY"] == "mock_key"
    assert headers["ACCESS-PASSPHRASE"] == "mock_passphrase"
    assert headers["Content-Type"] == "application/json"
    assert "ACCESS-SIGN" in headers
    assert "ACCESS-TIMESTAMP" in headers

@pytest.mark.asyncio
async def test_weex_dry_run_balance():
    adapter = WeexAdapter(
        api_key="mock_key",
        api_secret="mock_secret",
        passphrase="mock_passphrase",
        testnet=True,
        dry_run=True
    )
    balance = await adapter.get_account_balance("USDT")
    assert balance == 10000.0

@pytest.mark.asyncio
async def test_weex_dry_run_smart_order():
    adapter = WeexAdapter(
        api_key="mock_key",
        api_secret="mock_secret",
        passphrase="mock_passphrase",
        testnet=True,
        dry_run=True
    )
    result = await adapter.execute_smart_order(
        symbol="BTCUSDT",
        side="BUY",
        entry_price=60000.0,
        sl_price=58000.0,
        tp_price=64000.0,
        quote_qty=100.0
    )
    assert result.success is True
    assert result.dry_run is True
    assert result.symbol == "BTCUSDT_UMCBL"
    assert result.side == "BUY"
    assert result.entry_order["status"] == "FILLED"
    assert result.entry_order["executedQty"] is not None
    assert result.oco_order["type"] == "SIMULATED_OCO"
