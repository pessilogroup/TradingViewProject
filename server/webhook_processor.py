"""
P8: Shared Webhook Signal Processor
════════════════════════════════════════════════════════════════
Xử lý signal từ TradingView — dùng bởi cả FastAPI endpoint
và Telegram Bot (qua Cloudflare Worker).

Tách riêng 2 bước:
  1. save_signal()   — lưu signal + RAG analysis (luôn chạy ngay)
  2. execute_signal() — đặt lệnh Binance (chạy khi user confirm)
════════════════════════════════════════════════════════════════
"""

import json
import logging
from typing import Optional, Dict, Any

import config
import database
import notifier

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# STEP 1: SAVE SIGNAL + RAG ANALYSIS
# ═══════════════════════════════════════════════════════════════

async def save_signal(
    symbol: str,
    action: str,
    price: str,
    quote_qty: float = 10,
    source: str = "webhook",
    source_ip: str = "telegram",
    payload: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Lưu signal vào database + chạy RAG analysis.
    Trả về dict chứa signal_id và rag_advice.

    Bước này luôn chạy ngay khi nhận signal (không cần confirm).
    """
    if payload is None:
        payload = {}

    # Enrich payload with source
    payload["_source"] = source
    payload["_processor"] = "webhook_processor"

    # Parse price
    try:
        price_float = float(price) if price else None
    except (ValueError, TypeError):
        price_float = None

    # Save signal to database
    signal_id = await database.insert_signal(
        symbol=symbol,
        action=action,
        price=price_float,
        quote_qty=float(quote_qty) if quote_qty else None,
        source_ip=source_ip,
        payload=payload,
    )

    log.info(
        f"SIGNAL #{signal_id} [via {source}] action={action} "
        f"symbol={symbol} price={price} qty={quote_qty}"
    )

    # ── RAG Analysis ─────────────────────────────────────────
    rag_advice = ""
    try:
        import rag
        if config.RAG_ENABLED and rag._collection is not None:
            query = rag.build_rag_query(symbol, action, payload)
            chunks = rag.query_knowledge(query, n_results=config.RAG_TOP_K)
            if chunks:
                rag_advice = await rag.generate_trading_advice(
                    symbol=symbol,
                    action=action,
                    price=price,
                    payload=payload,
                    rag_chunks=chunks,
                )
    except Exception as e:
        log.error(f"RAG analysis error: {e}")
        rag_advice = ""

    return {
        "signal_id": signal_id,
        "symbol": symbol,
        "action": action,
        "price": price,
        "quote_qty": quote_qty,
        "rag_advice": rag_advice,
        "source": source,
    }


# ═══════════════════════════════════════════════════════════════
# STEP 2: EXECUTE TRADE (after user confirmation)
# ═══════════════════════════════════════════════════════════════

async def execute_signal(
    signal_id: int,
    symbol: str,
    action: str,
    price: str,
    quote_qty: float = 10,
    rag_advice: str = "",
) -> Dict[str, Any]:
    """
    Đặt lệnh Binance và gửi notification.
    Chỉ gọi function này sau khi user đã confirm.

    Returns dict with execution result.
    """
    import binance_client as binance_module

    action_lower = action.lower()

    # Chỉ execute nếu action là buy/sell
    if action_lower not in ("buy", "sell"):
        # Notification-only signal
        await database.update_signal_status(signal_id, 1)

        msg = (
            f"📡 **Tín hiệu TradingView**\n"
            f"- Mã: `{symbol}`\n"
            f"- Hành động: `{action.upper()}`\n"
            f"- Giá: `{price}`\n"
            f"- Signal ID: `#{signal_id}`"
        )
        if rag_advice:
            msg += f"\n\n🧠 **Phân tích Minervini AI:**\n{rag_advice}"

        await notifier.notify_all(msg)

        return {
            "success": True,
            "signal_id": signal_id,
            "action": "notify_only",
            "order": None,
        }

    # ── Trade execution ──────────────────────────────────────
    client = binance_module.get_client()
    entry_price = float(price) if price else 0

    try:
        result = client.execute_smart_order(
            symbol=symbol,
            side=action.upper(),
            entry_price=entry_price,
            quote_qty=quote_qty if quote_qty else None,
        )
        result = await result

        if result.success:
            entry = result.entry_order
            order_id = str(entry.get("orderId", "N/A"))
            order_status = entry.get("status", "FILLED")
            exec_qty = float(entry.get("executedQty", 0))
            cum_quote = float(entry.get("cummulativeQuoteQty", 0))
            exec_price = cum_quote / exec_qty if exec_qty > 0 else None

            order_type = "DRY_RUN" if result.dry_run else "OCO"
            oco_id = None
            if result.oco_order:
                oco_id = str(result.oco_order.get("orderListId", ""))

            trade_id = await database.insert_trade(
                signal_id=signal_id,
                symbol=symbol,
                side=action.upper(),
                order_id=order_id,
                status=order_status,
                requested_qty=quote_qty,
                executed_qty=exec_qty,
                executed_price=exec_price,
            )

            if result.risk:
                await database.update_trade_oco(
                    trade_id=trade_id,
                    stop_loss_price=result.risk.stop_loss_price,
                    take_profit_price=result.risk.take_profit_price,
                    oco_order_id=oco_id,
                    order_type=order_type,
                )

            await database.update_signal_status(signal_id, 1)

            msg = binance_module.format_order_telegram(result)
            if rag_advice:
                msg += f"\n\n🧠 **Phân tích Minervini AI:**\n{rag_advice}"

            log.info(f"Smart Order Success: {order_id} (type={order_type})")
            await notifier.notify_all(msg)

            return {
                "success": True,
                "signal_id": signal_id,
                "action": "trade_executed",
                "order_id": order_id,
                "order_type": order_type,
            }

        else:
            raise Exception(result.error or "Smart order failed")

    except Exception as e:
        error_msg = str(e)
        log.error(f"Trade Execution Failed: {error_msg}")

        await database.insert_trade(
            signal_id=signal_id,
            symbol=symbol,
            side=action.upper(),
            requested_qty=float(quote_qty) if quote_qty else 0,
            error_message=error_msg,
            status="FAILED",
        )
        await database.update_signal_status(signal_id, 2)

        msg = (
            f"❌ **Lỗi Đặt Lệnh Binance**\n"
            f"- Mã: `{symbol}`\n"
            f"- Lệnh: `{action.upper()}`\n"
            f"- Chi tiết lỗi: `{error_msg}`\n"
            f"- Signal ID: `#{signal_id}`"
        )
        await notifier.notify_all(msg)

        return {
            "success": False,
            "signal_id": signal_id,
            "action": "trade_failed",
            "error": error_msg,
        }


# ═══════════════════════════════════════════════════════════════
# CONVENIENCE: Full pipeline (save + execute, for FastAPI backward compat)
# ═══════════════════════════════════════════════════════════════

async def process_webhook_signal(
    symbol: str,
    action: str,
    price: str,
    quote_qty: float = 10,
    source: str = "webhook",
    source_ip: str = "unknown",
    payload: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Full pipeline: save signal + execute immediately.
    Used by FastAPI /webhook endpoint (backward compatible, no confirm).
    """
    # Step 1: Save + RAG
    signal_data = await save_signal(
        symbol=symbol,
        action=action,
        price=price,
        quote_qty=quote_qty,
        source=source,
        source_ip=source_ip,
        payload=payload,
    )

    # Step 2: Execute immediately (no confirmation)
    action_lower = action.lower()
    if (config.BINANCE_API_KEY or config.BINANCE_DRY_RUN) and action_lower in ("buy", "sell"):
        exec_result = await execute_signal(
            signal_id=signal_data["signal_id"],
            symbol=symbol,
            action=action,
            price=price,
            quote_qty=quote_qty,
            rag_advice=signal_data.get("rag_advice", ""),
        )
        signal_data.update(exec_result)
    else:
        # Notification-only
        exec_result = await execute_signal(
            signal_id=signal_data["signal_id"],
            symbol=symbol,
            action=action,
            price=price,
            quote_qty=quote_qty,
            rag_advice=signal_data.get("rag_advice", ""),
        )
        signal_data.update(exec_result)

    return signal_data
