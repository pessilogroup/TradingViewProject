"""
test_vps_analyzer.py — Unit tests for VpsAnalyzerWorker (Phase 5).

Tests all methods of the VPS Analyzer Worker with mocked HTTP calls
and mocked RAG functions. No real network or AI calls are made.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from aiohttp import ClientResponseError

import config


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_vbs_signal(queue_id=1, symbol="BTCUSDT", action="buy", price=68000.0):
    """Create a sample VBS signal dict."""
    return {
        "queue_id": queue_id,
        "symbol": symbol,
        "action": action,
        "price": price,
        "quote_qty": 10.0,
        "age_minutes": 5.0,
        "interval": "1h",
        "payload": {
            "symbol": symbol,
            "action": action,
            "price": price,
            "alert_type": "vcp_breakout",
            "volume": 5000000,
            "volume_avg": 3000000,
            "exchange": "binance",
        },
    }


class FakeResponse:
    """Fake aiohttp response for mocking session.get/post."""

    def __init__(self, status=200, json_data=None, text_data=""):
        self.status = status
        self._json_data = json_data or {}
        self._text_data = text_data

    async def json(self):
        return self._json_data

    async def text(self):
        return self._text_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


# ── poll_and_analyze() ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_poll_and_analyze_success():
    """poll_and_analyze returns analyzed results for received signals."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()

    # Mock _analyze_signal to return a trade payload
    trade_payload = {
        "symbol": "BTCUSDT",
        "action": "buy",
        "price": 68000.0,
        "qty": 0.003,
        "sl": 62560.0,
        "tp": 81600.0,
    }
    worker._analyze_signal = AsyncMock(return_value=trade_payload)

    vbs_response = FakeResponse(
        status=200,
        json_data={"signals": [_make_vbs_signal(queue_id=42)]},
    )

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=vbs_response)
    worker.get_session = AsyncMock(return_value=mock_session)

    results = await worker.poll_and_analyze()

    assert len(results) == 1
    assert results[0]["queue_id"] == 42
    assert results[0]["approved"] is True
    assert results[0]["trade_payload"] == trade_payload
    worker._analyze_signal.assert_called_once()

    await worker.close()


@pytest.mark.asyncio
async def test_poll_and_analyze_empty_response():
    """poll_and_analyze returns empty list when VBS has no signals."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()
    vbs_response = FakeResponse(status=200, json_data={"signals": []})

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=vbs_response)
    worker.get_session = AsyncMock(return_value=mock_session)

    results = await worker.poll_and_analyze()
    assert results == []
    await worker.close()


@pytest.mark.asyncio
async def test_poll_and_analyze_vbs_http_error():
    """poll_and_analyze returns empty list on VBS HTTP error."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()
    vbs_response = FakeResponse(status=503, text_data="Service Unavailable")

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=vbs_response)
    worker.get_session = AsyncMock(return_value=mock_session)

    results = await worker.poll_and_analyze()
    assert results == []
    await worker.close()


@pytest.mark.asyncio
async def test_poll_and_analyze_vbs_connection_error():
    """poll_and_analyze returns empty list when VBS is unreachable."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()

    mock_session = MagicMock()
    mock_session.get = MagicMock(side_effect=Exception("Connection refused"))
    worker.get_session = AsyncMock(return_value=mock_session)

    results = await worker.poll_and_analyze()
    assert results == []
    await worker.close()


@pytest.mark.asyncio
async def test_poll_and_analyze_rejected_signal():
    """poll_and_analyze marks signal as rejected when _analyze_signal returns None."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()
    worker._analyze_signal = AsyncMock(return_value=None)

    vbs_response = FakeResponse(
        status=200,
        json_data={"signals": [_make_vbs_signal(queue_id=99)]},
    )

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=vbs_response)
    worker.get_session = AsyncMock(return_value=mock_session)

    results = await worker.poll_and_analyze()

    assert len(results) == 1
    assert results[0]["queue_id"] == 99
    assert results[0]["approved"] is False
    assert "rejected" in results[0]["reason"].lower() or "criteria" in results[0]["reason"].lower()
    await worker.close()


@pytest.mark.asyncio
async def test_poll_and_analyze_analysis_exception():
    """poll_and_analyze handles exception in _analyze_signal gracefully."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()
    worker._analyze_signal = AsyncMock(side_effect=RuntimeError("RAG crashed"))

    vbs_response = FakeResponse(
        status=200,
        json_data={"signals": [_make_vbs_signal(queue_id=88)]},
    )

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=vbs_response)
    worker.get_session = AsyncMock(return_value=mock_session)

    results = await worker.poll_and_analyze()

    assert len(results) == 1
    assert results[0]["queue_id"] == 88
    assert results[0]["approved"] is False
    assert "error" in results[0]["reason"].lower()
    await worker.close()


# ── _analyze_signal() ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analyze_signal_approved():
    """_analyze_signal returns trade payload when AI approves the signal."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()
    signal = _make_vbs_signal(queue_id=10, price=50000.0)

    with patch("rag.build_rag_query", return_value="VCP breakout query"), \
         patch("rag.query_knowledge", return_value=[{"content": "chunk", "metadata": {}, "relevance_score": 0.9}]), \
         patch("rag.generate_trading_advice", new_callable=AsyncMock, return_value="🟢 Tín hiệu Mạnh. Nên BUY tại pivot. SL -8%."):

        result = await worker._analyze_signal(signal)

    assert result is not None
    assert result["symbol"] == "BTCUSDT"
    assert result["action"] == "buy"
    assert result["price"] == 50000.0
    assert result["qty"] > 0
    assert result["sl"] > 0
    assert result["tp"] > 0
    assert "analysis" in result
    await worker.close()


@pytest.mark.asyncio
async def test_analyze_signal_rejected_by_ai():
    """_analyze_signal returns None when AI rejects with warning keywords."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()
    signal = _make_vbs_signal(queue_id=11, price=50000.0)

    with patch("rag.build_rag_query", return_value="test query"), \
         patch("rag.query_knowledge", return_value=[{"content": "chunk", "metadata": {}, "relevance_score": 0.5}]), \
         patch("rag.generate_trading_advice", new_callable=AsyncMock, return_value="⚠️ RAG Analysis không khả dụng (thiếu API key)."):

        result = await worker._analyze_signal(signal)

    assert result is None
    await worker.close()


@pytest.mark.asyncio
async def test_analyze_signal_invalid_price():
    """_analyze_signal returns None for zero/invalid price."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()
    signal = _make_vbs_signal(queue_id=12, price=0)

    with patch("rag.build_rag_query", return_value="test query"), \
         patch("rag.query_knowledge", return_value=[]), \
         patch("rag.generate_trading_advice", new_callable=AsyncMock, return_value="Buy signal looks good"):

        result = await worker._analyze_signal(signal)

    assert result is None
    await worker.close()


@pytest.mark.asyncio
async def test_analyze_signal_position_sizing():
    """_analyze_signal computes correct position sizing from config."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()
    signal = _make_vbs_signal(queue_id=13, price=100.0, action="buy")

    # With defaults: RISK_PER_TRADE=0.02, STOP_LOSS_PCT=0.08, MAX_QUOTE_QTY=1000
    # risk_amount = 1000 * 0.02 = 20
    # dollar_risk_per_unit = 100 * 0.08 = 8
    # qty = 20 / 8 = 2.5
    # quote_value = 2.5 * 100 = 250 <= 1000 (under cap)
    # sl = 100 * (1 - 0.08) = 92
    # tp = 100 * (1 + 0.20) = 120

    with patch("rag.build_rag_query", return_value="test query"), \
         patch("rag.query_knowledge", return_value=[{"content": "chunk", "metadata": {}, "relevance_score": 0.9}]), \
         patch("rag.generate_trading_advice", new_callable=AsyncMock, return_value="Strong BUY signal."):

        result = await worker._analyze_signal(signal)

    assert result is not None
    assert result["qty"] == 2.5
    assert result["sl"] == 92.0
    assert result["tp"] == 120.0
    await worker.close()


@pytest.mark.asyncio
async def test_analyze_signal_sell_position_sizing():
    """_analyze_signal computes correct SL/TP for sell signals."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()
    signal = _make_vbs_signal(queue_id=14, price=100.0, action="sell")

    # For sell: sl = 100 * (1 + 0.08) = 108, tp = 100 * (1 - 0.20) = 80

    with patch("rag.build_rag_query", return_value="test query"), \
         patch("rag.query_knowledge", return_value=[{"content": "chunk", "metadata": {}, "relevance_score": 0.9}]), \
         patch("rag.generate_trading_advice", new_callable=AsyncMock, return_value="Strong SELL signal. Bán ngay."):

        result = await worker._analyze_signal(signal)

    assert result is not None
    assert result["sl"] == 108.0
    assert result["tp"] == 80.0
    await worker.close()


# ── forward_to_server_b() ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_forward_to_server_b_success():
    """forward_to_server_b returns success when Server B accepts trade."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()
    trade_payload = {
        "symbol": "BTCUSDT",
        "action": "buy",
        "price": 68000.0,
        "qty": 0.003,
        "sl": 62560.0,
        "tp": 81600.0,
        "analysis": "Buy approved",
    }

    server_b_response = FakeResponse(
        status=200,
        json_data={"status": "ok", "order_id": "ORD-456"},
    )

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=server_b_response)
    worker.get_session = AsyncMock(return_value=mock_session)

    result = await worker.forward_to_server_b(trade_payload)

    assert result["success"] is True
    assert result["status"] == 200
    assert result["data"]["order_id"] == "ORD-456"
    await worker.close()


@pytest.mark.asyncio
async def test_forward_to_server_b_unauthorized():
    """forward_to_server_b returns failure on 401 from Server B."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()
    trade_payload = {"symbol": "BTCUSDT", "action": "buy", "price": 68000.0}

    server_b_response = FakeResponse(
        status=401,
        json_data={"detail": "Invalid secret"},
    )

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=server_b_response)
    worker.get_session = AsyncMock(return_value=mock_session)

    result = await worker.forward_to_server_b(trade_payload)

    assert result["success"] is False
    assert result["status"] == 401
    assert "Invalid secret" in result["error"]
    await worker.close()


@pytest.mark.asyncio
async def test_forward_to_server_b_connection_error():
    """forward_to_server_b returns failure when Server B is unreachable."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()
    trade_payload = {"symbol": "BTCUSDT", "action": "buy", "price": 68000.0}

    mock_session = MagicMock()
    mock_session.post = MagicMock(side_effect=Exception("Connection refused"))
    worker.get_session = AsyncMock(return_value=mock_session)

    result = await worker.forward_to_server_b(trade_payload)

    assert result["success"] is False
    assert result["status"] == 0
    assert "Connection refused" in result["error"]
    await worker.close()


# ── _ack_signal() ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ack_signal_success():
    """_ack_signal returns True when VBS accepts the ACK."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()

    ack_response = FakeResponse(status=200, json_data={"ok": True})

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=ack_response)
    worker.get_session = AsyncMock(return_value=mock_session)

    result = await worker._ack_signal(42, "executed")

    assert result is True

    # Verify the POST was called with correct payload structure
    call_args = mock_session.post.call_args
    posted_json = call_args.kwargs.get("json") or call_args[1].get("json", {})
    assert "acks" in posted_json
    assert len(posted_json["acks"]) == 1
    assert posted_json["acks"][0]["queue_id"] == 42
    assert posted_json["acks"][0]["status"] == "executed"
    await worker.close()


@pytest.mark.asyncio
async def test_ack_signal_failure():
    """_ack_signal returns False when VBS rejects the ACK."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()

    ack_response = FakeResponse(status=500, text_data="Internal Server Error")

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=ack_response)
    worker.get_session = AsyncMock(return_value=mock_session)

    result = await worker._ack_signal(42, "executed")

    assert result is False
    await worker.close()


@pytest.mark.asyncio
async def test_ack_signal_connection_error():
    """_ack_signal returns False when VBS is unreachable."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()

    mock_session = MagicMock()
    mock_session.post = MagicMock(side_effect=Exception("Connection refused"))
    worker.get_session = AsyncMock(return_value=mock_session)

    result = await worker._ack_signal(42, "executed")

    assert result is False
    await worker.close()


# ── run() loop ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_loop_approved_signal():
    """run() forwards approved signals to Server B and ACKs them."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()
    worker.poll_interval = 0  # no sleep for tests

    analyzed_signals = [{
        "queue_id": 100,
        "approved": True,
        "trade_payload": {"symbol": "BTCUSDT", "action": "buy", "price": 68000.0},
    }]

    call_count = 0

    async def mock_poll():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return analyzed_signals
        # Cancel after first iteration
        raise asyncio.CancelledError()

    worker.poll_and_analyze = mock_poll
    worker.forward_to_server_b = AsyncMock(return_value={"success": True})
    worker._ack_signal = AsyncMock(return_value=True)

    await worker.run()

    worker.forward_to_server_b.assert_called_once_with(analyzed_signals[0]["trade_payload"])
    worker._ack_signal.assert_called_once_with(100, "executed")


@pytest.mark.asyncio
async def test_run_loop_rejected_signal():
    """run() ACKs rejected signals without forwarding."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()
    worker.poll_interval = 0

    analyzed_signals = [{
        "queue_id": 200,
        "approved": False,
        "reason": "Does not meet criteria",
    }]

    call_count = 0

    async def mock_poll():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return analyzed_signals
        raise asyncio.CancelledError()

    worker.poll_and_analyze = mock_poll
    worker.forward_to_server_b = AsyncMock()
    worker._ack_signal = AsyncMock(return_value=True)

    await worker.run()

    worker.forward_to_server_b.assert_not_called()
    worker._ack_signal.assert_called_once_with(200, "rejected", "Does not meet criteria")


@pytest.mark.asyncio
async def test_run_loop_server_b_failure():
    """run() ACKs with 'failed' status when Server B rejects the trade."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()
    worker.poll_interval = 0

    analyzed_signals = [{
        "queue_id": 300,
        "approved": True,
        "trade_payload": {"symbol": "ETHUSDT", "action": "buy", "price": 3500.0},
    }]

    call_count = 0

    async def mock_poll():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return analyzed_signals
        raise asyncio.CancelledError()

    worker.poll_and_analyze = mock_poll
    worker.forward_to_server_b = AsyncMock(
        return_value={"success": False, "error": "Insufficient margin"}
    )
    worker._ack_signal = AsyncMock(return_value=True)

    await worker.run()

    worker._ack_signal.assert_called_once_with(300, "failed", "Insufficient margin")


@pytest.mark.asyncio
async def test_run_loop_error_recovery():
    """run() continues after non-fatal exception in loop body."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()
    worker.poll_interval = 0

    call_count = 0

    async def mock_poll():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Transient network error")
        if call_count == 2:
            return []  # Recovered
        raise asyncio.CancelledError()

    worker.poll_and_analyze = mock_poll

    await worker.run()

    # Should have called poll 3 times (error, empty, cancel)
    assert call_count == 3


# ── Session management ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_session_creates_new():
    """get_session creates a new aiohttp.ClientSession."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()
    session = await worker.get_session()

    assert session is not None
    assert not session.closed

    await worker.close()
    assert session.closed


@pytest.mark.asyncio
async def test_get_session_reuses_existing():
    """get_session reuses existing session if not closed."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()
    session1 = await worker.get_session()
    session2 = await worker.get_session()

    assert session1 is session2

    await worker.close()


@pytest.mark.asyncio
async def test_close_idempotent():
    """close() is safe to call multiple times."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()
    await worker.get_session()

    await worker.close()
    await worker.close()  # Should not raise


# ── Multiple signals in one poll ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_poll_and_analyze_multiple_signals():
    """poll_and_analyze processes multiple signals with mixed results."""
    from workers.vps_analyzer import VpsAnalyzerWorker

    worker = VpsAnalyzerWorker()

    trade_payload = {"symbol": "BTCUSDT", "action": "buy", "price": 68000.0}
    call_index = 0

    async def mock_analyze(signal):
        nonlocal call_index
        call_index += 1
        if call_index == 1:
            return trade_payload  # approved
        return None  # rejected

    worker._analyze_signal = mock_analyze

    signals = [
        _make_vbs_signal(queue_id=50, symbol="BTCUSDT"),
        _make_vbs_signal(queue_id=51, symbol="ETHUSDT"),
    ]
    vbs_response = FakeResponse(status=200, json_data={"signals": signals})

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=vbs_response)
    worker.get_session = AsyncMock(return_value=mock_session)

    results = await worker.poll_and_analyze()

    assert len(results) == 2
    assert results[0]["approved"] is True
    assert results[0]["queue_id"] == 50
    assert results[1]["approved"] is False
    assert results[1]["queue_id"] == 51
    await worker.close()
