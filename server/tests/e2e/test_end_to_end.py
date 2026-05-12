import pytest
import json
from httpx import AsyncClient, ASGITransport
import sys
import os

# Add server to path so we can import main
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from main import app
from database import init_db

# Load mock payloads
def load_payloads():
    import config
    payloads_path = os.path.join(os.path.dirname(__file__), '../mock_data/payloads.json')
    with open(payloads_path, 'r') as f:
        payloads = json.load(f)
    
    # Inject config.WEBHOOK_SECRET into payloads
    for key, payload in payloads.items():
        if key != "invalid_secret" and "secret" in payload:
            payload["secret"] = config.WEBHOOK_SECRET
    return payloads

@pytest.fixture(autouse=True)
async def setup_test_db():
    # Use memory database for tests or a test file
    import config
    config.DB_NAME = ":memory:"
    await init_db()
    global PAYLOADS
    PAYLOADS = load_payloads()
    yield

@pytest.mark.asyncio
async def test_valid_1h_buy_webhook(mocker):
    # Mock Telegram and Binance
    mocker.patch('main.notifier.notify_all', return_value=True)
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post("/webhook", json=PAYLOADS["valid_1h_buy"])
        
    assert response.status_code == 200
    data = response.json()
    assert data["received"] is True
    assert data["status"] == "processing_async"
    assert "signal_id" in data

@pytest.mark.asyncio
async def test_invalid_4h_buy_webhook(mocker):
    mocker.patch('main.notifier.notify_all', return_value=True)
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post("/webhook", json=PAYLOADS["invalid_4h_buy"])
        
    assert response.status_code == 200
    data = response.json()
    assert data["received"] is True
    assert data["status"] == "rejected"
    assert data["reason"] == "invalid_timeframe"

@pytest.mark.asyncio
async def test_invalid_secret_webhook():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post("/webhook", json=PAYLOADS["invalid_secret"])
        
    assert response.status_code == 401
    assert response.json()["detail"] == "Unauthorized"

@pytest.mark.asyncio
async def test_missing_interval_webhook(mocker):
    mocker.patch('main.notifier.notify_all', return_value=True)
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post("/webhook", json=PAYLOADS["missing_interval"])
        
    assert response.status_code == 200
    data = response.json()
    assert data["received"] is True
    assert data["status"] == "rejected"
    assert data["reason"] == "invalid_timeframe"
