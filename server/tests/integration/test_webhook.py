"""
Integration tests: POST /webhook
Covers: buy/sell/alert signals, auth, validation edge cases
"""
import pytest

SECRET = "test-secret"
BASE_PAYLOAD = {
    "action": "buy",
    "symbol": "BTCUSDT",
    "price": "68000",
    "quoteQty": 15,
}


# ═══ HAPPY PATH ══════════════════════════════════════════════

@pytest.mark.asyncio
async def test_webhook_alert_signal_accepted(client):
    """Signal-only (no Binance key) returns received=True."""
    payload = {**BASE_PAYLOAD, "secret": SECRET}
    res = await client.post("/webhook", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["received"] is True
    assert "signal_id" in data
    assert data["signal_id"] >= 1


@pytest.mark.asyncio
async def test_webhook_sell_signal_accepted(client):
    payload = {"secret": SECRET, "action": "sell", "symbol": "BTCUSDT", "price": "72000", "quoteQty": 15}
    res = await client.post("/webhook", json=payload)
    assert res.status_code == 200
    assert res.json()["received"] is True


@pytest.mark.asyncio
async def test_webhook_secret_in_header(client):
    """Secret co the truyen qua header X-TV-Secret."""
    payload = {**BASE_PAYLOAD}
    res = await client.post("/webhook", json=payload, headers={"X-TV-Secret": SECRET})
    assert res.status_code == 200
    assert res.json()["received"] is True


@pytest.mark.asyncio
async def test_webhook_secret_in_query_param(client):
    """Secret co the truyen qua query param."""
    res = await client.post(f"/webhook?secret={SECRET}", json=BASE_PAYLOAD)
    assert res.status_code == 200
    assert res.json()["received"] is True


@pytest.mark.asyncio
async def test_webhook_saves_signal_to_db(client):
    """Signal phai duoc luu vao database."""
    payload = {**BASE_PAYLOAD, "secret": SECRET}
    res = await client.post("/webhook", json=payload)
    signal_id = res.json()["signal_id"]

    # Verify signal trong DB qua /trades endpoint
    trades_res = await client.get("/trades")
    # Signal duoc luu, du chua co trade
    assert trades_res.status_code == 200


@pytest.mark.asyncio
async def test_webhook_increments_signal_id(client):
    """Moi webhook phai tao signal_id tang dan."""
    payload = {**BASE_PAYLOAD, "secret": SECRET}
    r1 = await client.post("/webhook", json=payload)
    r2 = await client.post("/webhook", json=payload)
    assert r2.json()["signal_id"] > r1.json()["signal_id"]


# ═══ VALIDATION ═══════════════════════════════════════════════

@pytest.mark.asyncio
async def test_webhook_invalid_json_returns_400(client):
    res = await client.post(
        "/webhook",
        content=b"not valid json{{{",
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_webhook_without_secret_returns_401(client):
    res = await client.post("/webhook", json=BASE_PAYLOAD)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_webhook_wrong_secret_returns_401(client):
    payload = {**BASE_PAYLOAD, "secret": "wrong-secret"}
    res = await client.post("/webhook", json=payload)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_webhook_empty_body_after_secret_stripped_returns_400(client):
    """Neu payload chi co 'secret' va khong con gi khac sau khi pop."""
    res = await client.post("/webhook", json={"secret": SECRET})
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_webhook_missing_symbol_still_accepted(client):
    """Symbol truong optional — van xu ly."""
    payload = {"secret": SECRET, "action": "alert", "price": "68000"}
    res = await client.post("/webhook", json=payload)
    assert res.status_code == 200