"""
Security tests: authentication, IP whitelist
"""
import pytest


# ═══ AUTHENTICATION ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_no_secret_returns_401(client):
    """Khong co secret -> 401."""
    res = await client.post("/webhook", json={
        "action": "buy", "symbol": "BTCUSDT", "price": "68000"
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_wrong_secret_returns_401(client):
    """Secret sai -> 401."""
    res = await client.post("/webhook", json={
        "secret": "hacker123", "action": "buy", "symbol": "BTCUSDT"
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_empty_string_secret_returns_401(client):
    res = await client.post("/webhook", json={
        "secret": "", "action": "buy", "symbol": "BTCUSDT"
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_correct_secret_in_payload_returns_200(client):
    res = await client.post("/webhook", json={
        "secret": "test-secret", "action": "alert", "symbol": "BTCUSDT", "price": "68000"
    })
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_correct_secret_in_header_returns_200(client):
    res = await client.post(
        "/webhook",
        json={"action": "alert", "symbol": "BTCUSDT", "price": "68000"},
        headers={"X-TV-Secret": "test-secret"},
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_header_secret_overrides_payload(client):
    """Neu co ca header lan payload secret, header duoc uu tien."""
    res = await client.post(
        "/webhook",
        json={"secret": "wrong-one", "action": "alert", "symbol": "BTCUSDT"},
        headers={"X-TV-Secret": "test-secret"},
    )
    # Header dung -> phai pass
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_sql_injection_in_symbol_is_safe(client):
    """Symbol chua SQL injection khong duoc phep pha vo DB."""
    payload = {
        "secret": "test-secret",
        "action": "buy",
        "symbol": "BTCUSDT'; DROP TABLE trades; --",
        "price": "68000",
    }
    res = await client.post("/webhook", json=payload)
    # Phai xu ly binh thuong, khong crash server
    assert res.status_code == 200

    # DB van hoat dong
    stats = await client.get("/trades/stats")
    assert stats.status_code == 200


# ═══ IP WHITELIST ═════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ip_whitelist_disabled_allows_all(client):
    """ENABLE_IP_WHITELIST=false -> tat ca IP duoc phep."""
    import config
    config.ENABLE_IP_WHITELIST = False
    res = await client.get("/tv_health_check")
    assert res.status_code == 200
    config.ENABLE_IP_WHITELIST = False  # reset


@pytest.mark.asyncio
async def test_health_endpoint_not_protected_by_auth(client):
    """Health check khong can authentication."""
    res = await client.get("/tv_health_check")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_trades_endpoint_not_protected_by_auth(client):
    """/trades khong can auth (dashboard co the doc)."""
    res = await client.get("/trades")
    assert res.status_code == 200