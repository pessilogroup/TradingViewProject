"""
Security tests: test_auth.py
Tests Webhook authentication (secret validation) and missing secrets.
BUG-05 fix: test_dashboard_auth_unauthorized previously had no assertion.
"""
import pytest
import config


@pytest.mark.asyncio
async def test_webhook_missing_secret(client):
    """Webhook should reject requests without a secret."""
    payload = {"symbol": "BTCUSDT", "side": "BUY"}
    response = await client.post("/webhook", json=payload)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_invalid_secret_payload(client):
    """Webhook should reject requests with an invalid secret in payload."""
    payload = {"symbol": "BTCUSDT", "side": "BUY", "secret": "wrong-secret"}
    response = await client.post("/webhook", json=payload)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_valid_secret_payload(client):
    """Webhook should accept requests with the correct secret in payload."""
    payload = {"symbol": "BTCUSDT", "side": "BUY", "secret": "test-secret"}
    response = await client.post("/webhook", json=payload)
    assert response.status_code != 401  # May be 200 or 422 if payload is incomplete, but not 401


@pytest.mark.asyncio
async def test_webhook_invalid_secret_header(client):
    """Webhook should reject requests with an invalid secret in headers."""
    headers = {"Authorization": "wrong-secret"}
    response = await client.post("/webhook", json={"symbol": "BTCUSDT"}, headers=headers)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_auth_unauthorized(client):
    """
    BUG-05 fix: Added concrete assertion.
    When DASHBOARD_TOKEN="" (as set by conftest.py), the dashboard auth
    middleware is DISABLED — /api/system/status must be openly accessible (200).
    """
    response = await client.get("/api/system/status")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_auth_with_token_required(client):
    """
    When DASHBOARD_TOKEN is set, /api/* endpoints require Bearer token auth.
    Requests without a valid token should be rejected with 401.

    SEC-005: Only Authorization header is accepted (no ?token= query param).
    """
    original_token = config.DASHBOARD_TOKEN
    try:
        config.DASHBOARD_TOKEN = "secure-test-token"
        response = await client.get("/api/trades")
        assert response.status_code == 401
        # SEC-005: updated error message reflects header-only auth requirement
        assert response.json().get("error") == "Invalid or missing Authorization header"
    finally:
        # Always restore to avoid polluting other tests
        config.DASHBOARD_TOKEN = original_token