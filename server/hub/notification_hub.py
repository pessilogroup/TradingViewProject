"""
NotificationHub — Centralized notification subscriber for rejected signals.

Listens to: SignalRejected
Emits: (none — terminal subscriber)

Design Invariants:
- Phase 4 scope: Only handles SignalRejected notifications.
  TradeEngine and AIAnalyzer keep inline notification (Phase 3).
- Phase 5 will migrate ALL notification calls here.
- Uses set_bus() pattern for test isolation.
"""
import logging

import notifier

from core.event_bus import bus as _default_bus
from core.events import SignalRejected, AnalysisComplete, TradeApproved

log = logging.getLogger(__name__)

# Allow bus override for testing
_bus = _default_bus


def set_bus(bus_instance) -> None:
    """Override the event bus instance (for testing)."""
    global _bus
    _bus = bus_instance


def get_bus():
    """Get the current event bus instance."""
    return _bus


# ═══════════════════════════════════════════════════════════════
# EVENT HANDLERS
# ═══════════════════════════════════════════════════════════════

@_default_bus.on(SignalRejected)
async def notify_signal_rejected(event: SignalRejected) -> None:
    """
    Send Telegram/Discord notification when a signal is rejected.

    Rejection reasons:
    - duplicate_signal: Same (symbol, action) within 60s dedup window.
    - invalid_timeframe: Interval not in {60, 1h, 60m}.
    """
    reason_map = {
        "duplicate_signal": "Tín hiệu trùng lặp (dedup 60s)",
        "invalid_timeframe": f"Khung thời gian không hợp lệ: `{event.interval}`",
    }

    reason_text = reason_map.get(event.reason, event.reason)

    msg = (
        f"⛔ **Tín Hiệu Bị Từ Chối**\n"
        f"- Sàn: `{getattr(event, 'exchange', 'binance').upper()}`\n"
        f"- Mã: `{event.symbol}`\n"
        f"- Hành động: `{event.action.upper()}`\n"
        f"- Lý do: {reason_text}\n"
        f"- Signal ID: `#{event.signal_id}`"
    )

    if event.reason == "invalid_timeframe":
        msg += (
            f"\n\n💡 Chiến lược MIS v1 chỉ cho phép khung 1H (60). "
            f"Vui lòng kiểm tra cài đặt TradingView Alert."
        )

    log.info(f"NotificationHub: Rejected signal #{event.signal_id} on {getattr(event, 'exchange', 'binance')} — {event.reason}")
    await notifier.notify_all(msg)


# ═══════════════════════════════════════════════════════════════
# INTERACTIVE GATE (AnalysisComplete -> TradeApproved)
# ═══════════════════════════════════════════════════════════════

PENDING_TRADES = {}

@_default_bus.on(AnalysisComplete)
async def process_analysis_complete(event: AnalysisComplete) -> None:
    """
    Evaluate AI analysis results.
    If 'All Green', automatically approve the trade.
    If 'interactive_required', pause and send an interactive Telegram message to Human.
    """
    if event.should_trade and not event.interactive_required:
        log.info(f"NotificationHub: Auto-approving trade for #{event.signal_id} {event.symbol}")
        await _bus.emit(TradeApproved(
            signal_id=event.signal_id,
            symbol=event.symbol,
            action=event.action,
            price=event.price,
            quote_qty=event.quote_qty,
            sl=event.sl,
            tp=event.tp,
            approved_by="AI (Auto-Green)",
            analysis_text=event.analysis_text
        ))
    elif event.interactive_required or not event.should_trade:
        # If should_trade=False but we still want to give human a chance, or if interactive_required
        log.info(f"NotificationHub: Interactive approval required for #{event.signal_id} {event.symbol}")
        PENDING_TRADES[event.signal_id] = event
        
        msg = (
            f"⚠️ **CẦN DUYỆT LỆNH (Interactive Gate)**\n"
            f"- Sàn: `{getattr(event, 'exchange', 'binance').upper()}`\n"
            f"- Mã: `{event.symbol}`\n"
            f"- Hành động: `{event.action.upper()}`\n"
            f"- Giá: `{event.price or 'Market'}`\n"
            f"- Điểm AI: `{event.confidence}/10`\n\n"
            f"🧠 **Khuyến nghị AI:**\n{event.analysis_text}"
        )
        
        try:
            import telegram_bot
            sent_pairs = await telegram_bot.send_interactive_trade_approval(
                signal_id=event.signal_id,
                message=msg
            )
            if not sent_pairs:
                # Fallback to normal notify if bot not running
                await notifier.notify_all(msg + "\n\n*(Bot chưa bật, không thể dùng nút bấm duyệt lệnh)*")
            else:
                # REQ7: Register sent messages with ApprovalTimeoutManager for auto-timeout
                timeout_mgr = telegram_bot.get_approval_timeout_mgr()
                if timeout_mgr and isinstance(sent_pairs, list):
                    for chat_id, message_id in sent_pairs:
                        timeout_mgr.track_message(event.signal_id, chat_id, message_id)
        except Exception as e:
            log.error(f"NotificationHub: Failed to trigger interactive message: {e}")
            await notifier.notify_all(msg + f"\n\n*(Lỗi tương tác: {e})*")


