"""
SignalEnricher — Bridges IndicatorSignalValidated into the main pipeline.

Design Invariant DI-2:
    For entry/exit signals: emit SignalValidated (ATR-based SL/TP) → TradeEngine path.
    For info signals: notify directly via notifier (no trade execution, no AIAnalyzer screenshot).

REQ 5: ATR-based SL/TP computation
REQ 6: Informational signals notify only, no trade trigger
"""
import logging
from typing import Tuple, Optional

import notifier as _notifier
from core.event_bus import bus
from core.events import IndicatorSignalValidated, SignalValidated, SignalRejected

log = logging.getLogger(__name__)

_bus = bus


def set_bus(bus_instance) -> None:
    """Override the event bus instance (for testing)."""
    global _bus
    _bus = bus_instance


def _compute_sl_tp(price: float, metadata: dict) -> Tuple[str, str]:
    """
    Compute SL/TP based on ATR or percentage defaults.

    REQ 5.1 / 5.2: ATR path — sl = price - (atr*2), tp = price + (atr*3)
    REQ 5.3: Default path — sl = price * 0.95, tp = price * 1.10
    Property 12 & 13.
    """
    try:
        atr_raw = metadata.get("atr_value")
        if atr_raw is not None:
            atr = float(atr_raw)
            if atr > 0:
                sl = price - (atr * 2)
                tp = price + (atr * 3)
                return f"{sl:.6f}", f"{tp:.6f}"
    except (ValueError, TypeError) as e:
        log.warning(f"SignalEnricher: atr_value parse error — using percentage defaults ({e})")

    # Default: 5% / 10%
    sl = price * 0.95
    tp = price * 1.10
    return f"{sl:.6f}", f"{tp:.6f}"


@bus.on(IndicatorSignalValidated)
async def enrich_indicator_signal(event: IndicatorSignalValidated) -> None:
    """
    Bridges IndicatorSignalValidated to the main execution pipeline.

    entry/exit → ATR-computed SL/TP → emit SignalValidated → TradeEngine
    info       → Vietnamese Telegram notification (REQ 6, no trade execution)
    """
    if event.signal_type in {"entry", "exit"}:
        # REQ 5.4: entry → buy, exit → sell
        action = "buy" if event.signal_type == "entry" else "sell"

        # REQ 5.1-5.3: ATR-based or percentage SL/TP
        if event.price is None:
            log.error(
                f"SignalEnricher: Cannot compute SL/TP — price is None "
                f"(indicator={event.indicator_name}, signal_id={event.signal_id})"
            )
            await _bus.emit(SignalRejected(
                signal_id=event.signal_id,
                symbol=event.symbol,
                action=action,
                reason="enrichment_failed",
                exchange=event.exchange,
            ))
            return

        metadata = event.metadata or {}
        sl, tp = _compute_sl_tp(event.price, metadata)

        # REQ 5.5: Emit enriched SignalValidated into existing pipeline
        await _bus.emit(SignalValidated(
            signal_id=event.signal_id,
            symbol=event.symbol,
            action=action,
            price=event.price,
            quote_qty=10.0,  # Default; risk manager may override
            sl=sl,
            tp=tp,
            exchange=event.exchange,
        ))

    else:
        # REQ 6.1-6.3: info → notify directly (no AIAnalyzer / no screenshot capture)
        conditions_str = ", ".join(event.conditions_met) if event.conditions_met else "Không có"
        priority_prefix = "🔴 **KHẨN CẤP** — " if event.confidence_score > 80 else ""

        msg = (
            f"{priority_prefix}📊 **Tín Hiệu Thông Tin — {event.indicator_name}**\n"
            f"- Mã: `{event.symbol}`\n"
            f"- Sàn: `{event.exchange.upper()}`\n"
            f"- Điều kiện: `{conditions_str}`\n"
            f"- Độ tin cậy: `{event.confidence_score}%`\n"
            f"- Signal ID: `#{event.signal_id}`"
        )

        log.info(
            f"SignalEnricher: info signal for {event.symbol} "
            f"({event.indicator_name}, confidence={event.confidence_score}%)"
        )
        try:
            await _notifier.notify_all(msg)
        except Exception as e:
            log.error(f"SignalEnricher: Telegram notify failed for info signal #{event.signal_id}: {e}")
