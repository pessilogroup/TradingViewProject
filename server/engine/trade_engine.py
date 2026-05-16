"""
TradeEngine — Multi-Exchange MARKET + OCO execution with risk management (v6.0).

Listens to: TradeApproved
Emits: TradeExecuted | TradeFailed

Design Invariants (v6.0):
- Subscribes ONLY to TradeApproved (from NotificationHub gate).
- Does NOT call notifier directly — all notifications delegated to NotificationHub
  via TradeExecuted / TradeFailed events.
- Hybrid Transitional: writes to DB directly AND emits events.
- Uses ExchangeRouter for multi-exchange adapter resolution.
- Uses set_bus() pattern for test isolation.
"""
import logging
from typing import Optional

import database

from core.event_bus import bus as _default_bus
from core.events import TradeApproved, TradeExecuted, TradeFailed

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
# ═══════════════════════════════════════════════════════════════
# EVENT HANDLER: TradeApproved → Execute Order
# ═══════════════════════════════════════════════════════════════

@_default_bus.on(TradeApproved)
async def execute_trade(event: TradeApproved) -> None:
    """
    Execute a validated trade signal on the target exchange.

    Steps:
    1. Parse SL/TP prices from event.
    2. Resolve exchange adapter via ExchangeRouter.
    3. Call adapter.execute_smart_order().
    4. On success: persist trade + OCO to DB, emit TradeExecuted.
    5. On failure: persist failed trade to DB, emit TradeFailed.
    6. v6.0: Notifications are handled by NotificationHub via events.
    """
    action = event.action.lower()
    if action not in ("buy", "sell"):
        log.info(f"TradeEngine: Skipping non-trade action '{action}' for #{event.signal_id}")
        return

    # ── Parse prices ─────────────────────────────────────────
    try:
        entry_price = float(str(event.price).replace(',', '')) if event.price else 0.0
    except (ValueError, TypeError):
        entry_price = 0.0

    try:
        sl_price = float(str(event.sl).replace(',', '')) if event.sl else None
    except (ValueError, TypeError):
        sl_price = None

    try:
        tp_price = float(str(event.tp).replace(',', '')) if event.tp else None
    except (ValueError, TypeError):
        tp_price = None

    # ── Resolve exchange adapter ─────────────────────────────
    from exchanges.router import get_router
    router = get_router()
    requested_exchange = getattr(event, 'exchange', 'binance')

    try:
        adapter = router.resolve_exchange({"exchange": requested_exchange})
        actual_exchange = adapter.exchange_id
    except Exception as e:
        error_msg = f"Exchange routing failed: {e}"
        log.error(f"TradeEngine: {error_msg}")
        await _handle_failure(event, action, error_msg, requested_exchange, None)
        return

    combined_score: Optional[str] = getattr(event, 'combined_score', None)

    try:
        # ── Execute smart order (MARKET + OCO) ───────────────
        result = await adapter.execute_smart_order(
            symbol=event.symbol,
            side=action.upper(),
            entry_price=entry_price,
            quote_qty=event.quote_qty if event.quote_qty else None,
            sl_price=sl_price,
            tp_price=tp_price,
        )

        if result.success:
            entry = result.entry_order
            order_id = str(entry.get("orderId", "N/A"))
            order_status = entry.get("status", "FILLED")
            exec_qty = float(entry.get("executedQty", 0))
            cum_quote = float(entry.get("cummulativeQuoteQty", 0))
            # BUG-03 fix: guard against ZeroDivisionError in DRY_RUN where executedQty=0
            exec_price = (cum_quote / exec_qty) if exec_qty > 0 else None

            order_type = "DRY_RUN" if result.dry_run else "OCO"
            oco_id = None
            if result.oco_order:
                oco_id = str(result.oco_order.get("orderListId", ""))

            # ── Persist to DB (Hybrid — direct write) ────────
            trade_id = await database.insert_trade(
                signal_id=event.signal_id,
                symbol=event.symbol,
                side=action.upper(),
                order_id=order_id,
                status=order_status,
                requested_qty=event.quote_qty,
                executed_qty=exec_qty,
                executed_price=exec_price,
                combined_score=combined_score,
                exchange=actual_exchange,
            )

            if result.risk:
                await database.update_trade_oco(
                    trade_id=trade_id,
                    stop_loss_price=result.risk.stop_loss_price,
                    take_profit_price=result.risk.take_profit_price,
                    oco_order_id=oco_id,
                    order_type=order_type,
                )

            await database.update_signal_status(event.signal_id, 1)

            # ── Build telegram message for event context ─────
            fallback_text = f" (Fallback from {requested_exchange.title()})" if actual_exchange != requested_exchange else ""
            msg = (
                f"✅ **Đã Đặt Lệnh {actual_exchange.title()}{fallback_text}**\n"
                f"- Mã: `{event.symbol}`\n"
                f"- Lệnh: `{action.upper()} {order_type}`\n"
                f"- Số lượng: `{exec_qty}` (Value: `~{cum_quote}$`)\n"
                # BUG-03 fix: exec_price may be None for DRY_RUN/zero-fill orders
                f"- Giá khớp: `{f'{exec_price:.4f}' if exec_price is not None else 'N/A'}`\n"
            )
            if result.risk:
                msg += (
                    f"- Cắt lỗ (SL): `{result.risk.stop_loss_price}`\n"
                    f"- Chốt lời (TP): `{result.risk.take_profit_price}`\n"
                )
            if result.dry_run:
                msg += "\n⚠️ `CHẾ ĐỘ DRY_RUN — KHÔNG KHỚP LỆNH THỰC TẾ`"

            if getattr(event, 'analysis_text', ""):
                msg += f"\n\n🧠 **Phân tích Minervini AI (Được duyệt bởi {event.approved_by}):**\n{event.analysis_text[:500]}"

            log.info(f"TradeEngine: Smart Order Success #{order_id} on {actual_exchange} (type={order_type})")

            # ── v6.0: Emit downstream event (NotificationHub handles notification) ──
            await _bus.emit(TradeExecuted(
                signal_id=event.signal_id,
                trade_id=trade_id,
                symbol=event.symbol,
                side=action.upper(),
                order_id=order_id,
                status=order_status,
                exchange=actual_exchange,
                executed_qty=exec_qty,
                executed_price=exec_price,
                quote_qty=event.quote_qty,
                stop_loss_price=result.risk.stop_loss_price if result.risk else None,
                take_profit_price=result.risk.take_profit_price if result.risk else None,
                oco_order_id=oco_id,
                order_type=order_type,
                combined_score=combined_score,
                rag_advice=getattr(event, 'analysis_text', ""),
                telegram_message=msg,
            ))
        else:
            raise Exception(result.error or "Smart order failed")

    except Exception as e:
        error_msg = str(e)
        log.error(f"TradeEngine: Execution Failed — {error_msg}")
        await _handle_failure(event, action, error_msg, requested_exchange, combined_score)


async def _handle_failure(event, action, error_msg, exchange, combined_score):
    """Handle trade execution failure: persist to DB and emit TradeFailed."""
    try:
        req_qty = float(event.quote_qty) if event.quote_qty else 0.0
    except (ValueError, TypeError):
        req_qty = 0.0

    # ── Persist failure to DB (Hybrid — direct write) ────
    await database.insert_trade(
        signal_id=event.signal_id,
        symbol=event.symbol,
        side=action.upper(),
        requested_qty=req_qty,
        error_message=error_msg,
        status="FAILED",
        combined_score=combined_score,
        exchange=exchange,
    )
    await database.update_signal_status(event.signal_id, 2)

    log.info(f"TradeEngine: Emitting TradeFailed for #{event.signal_id}")

    # ── v6.0: Emit failure event (NotificationHub handles notification) ──
    await _bus.emit(TradeFailed(
        signal_id=event.signal_id,
        symbol=event.symbol,
        side=action.upper(),
        error=error_msg,
        quote_qty=req_qty,
        exchange=exchange,
        combined_score=combined_score,
    ))



