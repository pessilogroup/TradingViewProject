"""
Unit tests for AIAnalyzer component (Phase 3).

Tests verify:
- Cooldown rejects duplicate captures within the window.
- AlertTriggered emission from SignalProcessor for alert actions.
- set_bus() pattern works for test isolation.
"""
import pytest
from unittest.mock import AsyncMock, patch

from core.event_bus import EventBus
from core.events import (
    SignalReceived, AlertTriggered, AnalysisComplete, SignalValidated,
)


# ═══════════════════════════════════════════════════════════════
# AI ANALYZER TESTS
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_cooldown_rejects_duplicate():
    """A second capture within COOLDOWN_SEC should be silently rejected."""
    from analyzer.ai_analyzer import process_alert, set_bus, reset_capture_state, LAST_CAPTURE_TIME
    import time

    test_bus = EventBus()
    set_bus(test_bus)
    reset_capture_state()

    events_emitted = []

    @test_bus.on(AnalysisComplete)
    async def on_complete(event):
        events_emitted.append(event)

    try:
        # Simulate a recent capture (within cooldown window)
        LAST_CAPTURE_TIME["BTCUSDT"] = time.time()

        with patch("analyzer.ai_analyzer.notifier") as mock_notifier:
            mock_notifier.notify_all = AsyncMock()

            event = AlertTriggered(
                signal_id=200, symbol="BTCUSDT", price="68000", quote_qty=50.0,
            )
            await process_alert(event)

            # Should NOT have emitted any events (cooldown active)
            assert len(events_emitted) == 0
            # Notifier should NOT have been called (cooldown = silent skip)
            mock_notifier.notify_all.assert_not_awaited()
    finally:
        from core.event_bus import bus as default_bus
        set_bus(default_bus)
        reset_capture_state()


@pytest.mark.asyncio
async def test_signal_processor_emits_alert_triggered():
    """SignalProcessor should emit AlertTriggered for action='alert'."""
    from processor.signal_processor import process_signal, reset_dedup_cache, set_bus as sp_set_bus

    test_bus = EventBus()
    sp_set_bus(test_bus)
    reset_dedup_cache()

    alert_events = []

    @test_bus.on(AlertTriggered)
    async def on_alert(event):
        alert_events.append(event)

    try:
        event = SignalReceived(
            signal_id=201, symbol="ETHUSDT", action="alert",
            price=3500.0, quote_qty=50.0,
        )
        await process_signal(event)

        assert len(alert_events) == 1
        assert alert_events[0].symbol == "ETHUSDT"
        assert alert_events[0].signal_id == 201
    finally:
        from core.event_bus import bus as default_bus
        sp_set_bus(default_bus)
        reset_dedup_cache()


@pytest.mark.asyncio
async def test_high_confidence_triggers_trade():
    """When AIAnalyzer emits AnalysisComplete with confidence >= 7,
    it should also emit SignalValidated for TradeEngine."""
    from analyzer.ai_analyzer import process_validated_signal, set_bus, reset_capture_state
    from pathlib import Path

    test_bus = EventBus()
    set_bus(test_bus)
    reset_capture_state()

    analysis_events = []

    @test_bus.on(AnalysisComplete)
    async def on_analysis(event):
        analysis_events.append(event)

    try:
        mock_vision_result = {
            "symbol": "BTCUSDT",
            "analysis": "Strong setup. Stop Loss: 65,000. Take Profit: 75,000. Score 8/10.",
            "confidence": 4,
            "patterns": ["VCP", "Stage 2"],
            "combined_score": "8.0/10",
            "error": None,
        }

        with patch("analyzer.ai_analyzer.config") as mock_config, \
             patch("analyzer.ai_analyzer.notifier") as mock_notifier, \
             patch("analyzer.ai_analyzer.database") as mock_db, \
             patch("analyzer.ai_analyzer.get_mcp_client") as mock_mcp_factory, \
             patch("analyzer.ai_analyzer.vision_module") as mock_vision:

            # Config
            mock_config.MCP_ENABLED = True

            # MCP
            mock_mcp = AsyncMock()
            mock_mcp.health_check = AsyncMock(return_value={"connected": True})
            mock_screenshot_path = Path(__file__).parent / "fake_screenshot.png"
            mock_screenshot_path.touch()  # Create a temp file
            mock_mcp.capture_screenshot = AsyncMock(return_value=str(mock_screenshot_path))
            mock_mcp_factory.return_value = mock_mcp

            # Vision
            mock_vision.analyze_chart_vision = AsyncMock(return_value=mock_vision_result)
            mock_vision.format_vision_telegram.return_value = "Vision text"

            # DB & Notifier
            mock_db.insert_brief = AsyncMock(return_value=1)
            mock_notifier.notify_all = AsyncMock()
            mock_notifier.send_telegram_photo = lambda *a, **kw: None

            event = SignalValidated(
                signal_id=202, symbol="BTCUSDT", action="buy", price=68000.0, quote_qty=50.0,
            )
            await process_validated_signal(event)

            # Should emit AnalysisComplete
            assert len(analysis_events) == 1
            assert analysis_events[0].confidence == 8
            assert analysis_events[0].should_trade is True

            # Cleanup
            mock_screenshot_path.unlink(missing_ok=True)
    finally:
        from core.event_bus import bus as default_bus
        set_bus(default_bus)
        reset_capture_state()
