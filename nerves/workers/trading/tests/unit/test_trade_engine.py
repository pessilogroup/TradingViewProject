"""
Unit tests for TradeEngine component (v6.0).

Tests verify:
- Successful trade emits TradeExecuted event.
- Failed trade emits TradeFailed event.
- Non-trade actions (e.g., 'alert') are skipped.
- set_bus() pattern works for test isolation.

v6.0: TradeEngine no longer imports notifier — all notifications
      are delegated to NotificationHub via TradeExecuted/TradeFailed events.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from core.event_bus import EventBus
from core.events import TradeApproved, TradeExecuted, TradeFailed


# ═══════════════════════════════════════════════════════════════
# MOCK FIXTURES
# ═══════════════════════════════════════════════════════════════

@dataclass
class MockRiskParams:
    entry_price: float = 68000.0
    stop_loss_price: float = 66000.0
    take_profit_price: float = 72000.0
    stop_loss_pct: float = 0.03
    take_profit_pct: float = 0.06
    risk_reward_ratio: float = 2.0
    quantity: float = 0.001
    cost: float = 68.0
    risk_amount: float = 20.0
    account_balance: float = 10000.0
    position_pct: float = 0.0068


@dataclass
class MockOrderResult:
    success: bool = True
    dry_run: bool = True
    side: str = "BUY"
    symbol: str = "BTCUSDT"
    entry_order: Dict[str, Any] = field(default_factory=lambda: {
        "orderId": "DRY-TEST-001",
        "status": "FILLED",
        "executedQty": "0.001",
        "cummulativeQuoteQty": "68.00",
    })
    oco_order: Optional[Dict[str, Any]] = field(default_factory=lambda: {
        "orderListId": "DRY-OCO-001",
    })
    risk: Optional[MockRiskParams] = field(default_factory=MockRiskParams)
    error: Optional[str] = None


def _make_mock_client(order_result=None):
    adapter = AsyncMock()
    adapter.exchange_id = "binance"
    if order_result is None:
        order_result = MockOrderResult()
    adapter.execute_smart_order = AsyncMock(return_value=order_result)
    return adapter


# ═══════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_successful_trade_emits_executed():
    """A validated buy signal should execute and emit TradeExecuted."""
    from engine.trade_engine import execute_trade, set_bus

    test_bus = EventBus()
    set_bus(test_bus)
    executed_events = []

    @test_bus.on(TradeExecuted)
    async def on_executed(event):
        executed_events.append(event)

    mock_client = _make_mock_client()

    try:
        with patch("exchanges.router.get_router") as mock_get_router, \
             patch("engine.trade_engine.database") as mock_db:

            mock_router = MagicMock()
            mock_router.resolve_exchange.return_value = mock_client
            mock_get_router.return_value = mock_router

            mock_db.insert_trade = AsyncMock(return_value=1)
            mock_db.update_trade_oco = AsyncMock()
            mock_db.update_signal_status = AsyncMock()

            # v6.0: TradeEngine subscribes to TradeApproved, not SignalValidated
            event = TradeApproved(
                signal_id=100, symbol="BTCUSDT", action="buy",
                price=68000.0, quote_qty=50.0, sl="66000", tp="72000",
                approved_by="AI (Auto-Green)", analysis_text="Strong setup",
            )
            await execute_trade(event)

            # Verify trade was executed
            mock_client.execute_smart_order.assert_awaited_once()
            mock_db.insert_trade.assert_awaited_once()
            mock_db.update_trade_oco.assert_awaited_once()
            mock_db.update_signal_status.assert_awaited_once_with(100, 1)

            # Verify TradeExecuted event emitted
            assert len(executed_events) == 1
            assert executed_events[0].symbol == "BTCUSDT"
            assert executed_events[0].signal_id == 100
            assert executed_events[0].side == "BUY"
    finally:
        from core.event_bus import bus as default_bus
        set_bus(default_bus)


@pytest.mark.asyncio
async def test_failed_trade_emits_failed():
    """A trade failure should persist and emit TradeFailed."""
    from engine.trade_engine import execute_trade, set_bus

    test_bus = EventBus()
    set_bus(test_bus)
    failed_events = []

    @test_bus.on(TradeFailed)
    async def on_failed(event):
        failed_events.append(event)

    # Create a failing order result
    fail_result = MockOrderResult(success=False, error="Insufficient balance")
    mock_client = _make_mock_client(fail_result)

    try:
        with patch("exchanges.router.get_router") as mock_get_router, \
             patch("engine.trade_engine.database") as mock_db:

            mock_router = MagicMock()
            mock_router.resolve_exchange.return_value = mock_client
            mock_get_router.return_value = mock_router
            mock_db.insert_trade = AsyncMock(return_value=2)
            mock_db.update_signal_status = AsyncMock()

            # v6.0: TradeEngine subscribes to TradeApproved, not SignalValidated
            event = TradeApproved(
                signal_id=101, symbol="ETHUSDT", action="buy",
                price=3500.0, quote_qty=50.0,
                approved_by="Human", analysis_text="",
            )
            await execute_trade(event)

            # Verify failure was persisted
            mock_db.insert_trade.assert_awaited_once()
            call_kwargs = mock_db.insert_trade.call_args
            assert call_kwargs[1]["status"] == "FAILED"
            mock_db.update_signal_status.assert_awaited_once_with(101, 2)

            # Verify TradeFailed event emitted
            assert len(failed_events) == 1
            assert failed_events[0].symbol == "ETHUSDT"
            assert "Insufficient balance" in failed_events[0].error
    finally:
        from core.event_bus import bus as default_bus
        set_bus(default_bus)


@pytest.mark.asyncio
async def test_non_trade_action_skipped():
    """Non buy/sell actions should be skipped by TradeEngine."""
    from engine.trade_engine import execute_trade, set_bus

    test_bus = EventBus()
    set_bus(test_bus)
    events_emitted = []

    @test_bus.on(TradeExecuted)
    async def on_exec(event):
        events_emitted.append(event)

    @test_bus.on(TradeFailed)
    async def on_fail(event):
        events_emitted.append(event)

    try:
        # v6.0: TradeApproved with alert action should be skipped
        event = TradeApproved(
            signal_id=102, symbol="BTCUSDT", action="alert",
            price=68000.0, quote_qty=50.0,
            approved_by="AI", analysis_text="",
        )
        await execute_trade(event)

        # No events should be emitted
        assert len(events_emitted) == 0
    finally:
        from core.event_bus import bus as default_bus
        set_bus(default_bus)
