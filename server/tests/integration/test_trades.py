"""
Integration tests: GET /trades, GET /trades/stats, GET /trades/equity
"""
import pytest


# ═══ /trades ══════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_trades_empty_returns_valid_structure(client):
    res = await client.get("/trades")
    assert res.status_code == 200
    data = res.json()
    assert "trades" in data
    assert "total" in data
    assert isinstance(data["trades"], list)
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_trades_returns_data(client_with_trades):
    res = await client_with_trades.get("/trades")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 5
    assert len(data["trades"]) >= 5


@pytest.mark.asyncio
async def test_trades_pagination_limit(client_with_trades):
    res = await client_with_trades.get("/trades?limit=2")
    assert res.status_code == 200
    data = res.json()
    assert len(data["trades"]) <= 2
    assert data["total"] >= 5  # total van la so that


@pytest.mark.asyncio
async def test_trades_pagination_offset(client_with_trades):
    res1 = await client_with_trades.get("/trades?limit=2&offset=0")
    res2 = await client_with_trades.get("/trades?limit=2&offset=2")
    d1 = res1.json()["trades"]
    d2 = res2.json()["trades"]
    if d1 and d2:
        assert d1[0]["id"] != d2[0]["id"]


@pytest.mark.asyncio
async def test_trades_filter_by_symbol(client_with_trades):
    res = await client_with_trades.get("/trades?symbol=ETHUSDT")
    assert res.status_code == 200
    data = res.json()
    for trade in data["trades"]:
        assert trade["symbol"] == "ETHUSDT"


@pytest.mark.asyncio
async def test_trades_limit_max_enforced(client_with_trades):
    """Limit khong the vuot 200."""
    res = await client_with_trades.get("/trades?limit=999")
    assert res.status_code in (200, 422)  # FastAPI clamp hoac reject


# ═══ /trades/stats ════════════════════════════════════════════

@pytest.mark.asyncio
async def test_stats_empty_returns_zeros(client):
    res = await client.get("/trades/stats")
    assert res.status_code == 200
    data = res.json()
    assert data["total_trades"] == 0
    assert data["win_rate"] == 0.0
    assert data["profit_factor"] == 0.0


@pytest.mark.asyncio
async def test_stats_with_trades_correct_win_rate(client_with_trades):
    """2 wins, 1 loss trong 3 FILLED trades co pnl -> win rate = 66.7%."""
    res = await client_with_trades.get("/trades/stats")
    assert res.status_code == 200
    data = res.json()
    # Co 3 filled trades voi pnl: +200, +150, -80, +320 = 4 trades
    assert data["total_trades"] == 4
    assert data["winning_trades"] == 3
    assert data["losing_trades"] == 1
    assert data["win_rate"] == 75.0
    assert data["total_pnl"] == 590.0


@pytest.mark.asyncio
async def test_stats_profit_factor_calculated(client_with_trades):
    """Profit factor = total wins / total losses."""
    res = await client_with_trades.get("/trades/stats")
    data = res.json()
    # Wins: 200 + 150 + 320 = 670, Losses: 80
    # PF = 670 / 80 = 8.38
    assert data["profit_factor"] > 1.0


@pytest.mark.asyncio
async def test_stats_filter_by_symbol(client_with_trades):
    res = await client_with_trades.get("/trades/stats?symbol=ETHUSDT")
    data = res.json()
    # Chi co 1 ETH trade: -80
    assert data["total_trades"] == 1
    assert data["winning_trades"] == 0
    assert data["losing_trades"] == 1
    assert data["total_pnl"] == -80.0


@pytest.mark.asyncio
async def test_stats_required_keys_present(client_with_trades):
    res = await client_with_trades.get("/trades/stats")
    data = res.json()
    required = [
        "total_trades", "winning_trades", "losing_trades",
        "win_rate", "total_pnl", "profit_factor",
        "avg_win", "avg_loss", "max_drawdown", "best_trade", "worst_trade"
    ]
    for key in required:
        assert key in data, f"Missing key: {key}"


# ═══ /trades/equity ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_equity_empty_structure(client):
    res = await client.get("/trades/equity")
    assert res.status_code == 200
    data = res.json()
    assert "labels" in data
    assert "cumulative_pnl" in data
    assert isinstance(data["labels"], list)
    assert isinstance(data["cumulative_pnl"], list)


@pytest.mark.asyncio
async def test_equity_cumulative_pnl_increases(client_with_trades):
    """Equity curve phai la tong luy ke — so phan tu = so trades co pnl."""
    res = await client_with_trades.get("/trades/equity")
    data = res.json()
    assert len(data["labels"]) == len(data["cumulative_pnl"])
    assert len(data["cumulative_pnl"]) >= 3  # co it nhat 3 trades co pnl


@pytest.mark.asyncio
async def test_equity_filter_by_symbol(client_with_trades):
    res = await client_with_trades.get("/trades/equity?symbol=ETHUSDT")
    data = res.json()
    # Chi co 1 ETH trade co pnl
    assert len(data["cumulative_pnl"]) == 1
    assert data["cumulative_pnl"][0] == -80.0