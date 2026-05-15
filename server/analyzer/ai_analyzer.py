"""
AIAnalyzer — Stealth Capture + Vision AI + RAG analysis pipeline.

Listens to: AlertTriggered
Emits: AnalysisComplete, SignalValidated (when confidence >= 7)

Design Invariants:
- Owns LAST_CAPTURE_TIME state (architecture spec: AIAnalyzer owns last_capture_time).
- Hybrid Transitional: writes to DB directly AND emits events.
- Calls notifier directly (temporary — Phase 4 → NotificationHub).
- If confidence >= 7, emits SignalValidated → TradeEngine picks up.
"""
import logging
import re
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Optional

import config
import notifier
import database
import vision as vision_module
from mcp_client import get_mcp_client

from core.event_bus import bus as _default_bus
from core.events import AlertTriggered, AnalysisComplete, SignalValidated

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
# OWNED STATE — Stealth Capture Cooldown
# ═══════════════════════════════════════════════════════════════

LAST_CAPTURE_TIME: Dict[str, float] = {}
CAPTURE_COOLDOWN_SEC = 300  # 5 minutes per symbol


def reset_capture_state() -> None:
    """Clear capture cooldown state — for testing."""
    LAST_CAPTURE_TIME.clear()


# ═══════════════════════════════════════════════════════════════
# EVENT HANDLER
# ═══════════════════════════════════════════════════════════════

@_default_bus.on(AlertTriggered)
async def process_alert(event: AlertTriggered) -> None:
    """
    Handle stealth capture workflow for 'alert' actions.
    Just emit SignalValidated so the unified pipeline handles it.
    """
    log.info(f"AIAnalyzer: Stealth capture alert for {event.symbol} — routing to unified pipeline")
    await _bus.emit(SignalValidated(
        signal_id=event.signal_id,
        symbol=event.symbol,
        action="alert",
        price=float(event.price) if event.price else None,
        quote_qty=event.quote_qty,
        sl="",
        tp="",
        exchange=getattr(event, 'exchange', 'binance'),
    ))


@_default_bus.on(SignalValidated)
async def process_validated_signal(event: SignalValidated) -> None:
    """
    Unified AI Analysis Pipeline (Vision + RAG).
    1. Capture screenshot via MCP.
    2. Run Vision AI analysis.
    3. Run RAG Analysis asynchronously.
    4. Combine scores to determine if Human interaction is needed.
    5. Emit AnalysisComplete.
    """
    log.info(f"AIAnalyzer: Processing validated signal #{event.signal_id} for {event.symbol} (Action: {event.action})")
    
    symbol = event.symbol
    now = datetime.now(timezone.utc).timestamp()
    
    # ── Cooldown check (only for 'alert' actions) ────────────
    if event.action == "alert":
        last_time = LAST_CAPTURE_TIME.get(symbol, 0)
        if now - last_time < CAPTURE_COOLDOWN_SEC:
            log.warning(f"AIAnalyzer: Cooldown active for {symbol}. Skipping capture.")
            return
        LAST_CAPTURE_TIME[symbol] = now
    
    await notifier.notify_all(f"🤖 **AI Analysis:** Đang chụp ảnh và phân tích `{symbol}`...")

    screenshot_path = ""
    vision_result = {}
    analysis_text = ""
    confidence = 10
    should_trade = True
    interactive_required = False

    try:
        mcp = get_mcp_client()
        health = await mcp.health_check()
        if health.get("connected"):
            # ── Screenshot ───────────────────────────────────────
            ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_symbol = re.sub(r'[^A-Za-z0-9_\-]', '', symbol)
            save_path = Path(__file__).parent.parent / "screenshots" / f"stealth_{safe_symbol}_{ts_str}.png"

            screenshot_path = await mcp.capture_screenshot(
                symbol="active",
                timeframe="active",
                region="chart",
                save_path=save_path,
                active_only=True,
                crop=True,
            )

            if screenshot_path and Path(screenshot_path).exists():
                # ── Vision AI Analysis ───────────────────────────────
                vision_result = await vision_module.analyze_chart_vision(
                    image_path=Path(screenshot_path),
                    symbol=symbol,
                )
                
                if not vision_result.get("error"):
                    analysis_text += "👁️ **VISION AI:**\n" + vision_result.get("analysis", "") + "\n\n"
                    vision_conf = vision_result.get("confidence", 5)
                    # Adjust confidence based on vision
                    confidence = min(confidence, vision_conf * 2) # scale 1-5 to 1-10
                else:
                    analysis_text += f"❌ Vision Error: {vision_result['error']}\n\n"
        else:
            log.warning("AIAnalyzer: MCP not connected, skipping Vision AI.")
            analysis_text += "⚠️ TradingView MCP chưa kết nối. Bỏ qua phân tích hình ảnh.\n\n"
            
    except Exception as e:
        log.error(f"AIAnalyzer: Vision capture failed: {e}")
        analysis_text += f"❌ Lỗi chụp ảnh: {e}\n\n"

    # ── RAG Analysis ─────────────────────────────────────────
    if config.RAG_ENABLED:
        try:
            import rag
            payload = {"action": event.action, "symbol": event.symbol, "alert_type": "webhook"}
            query = rag.build_rag_query(event.symbol, event.action, payload)
            if rag._collection is not None:
                chunks = rag.query_knowledge(query, n_results=config.RAG_TOP_K)
                if chunks:
                    rag_advice = await rag.generate_trading_advice(
                        symbol=event.symbol,
                        action=event.action,
                        price=str(event.price) if event.price else "Market",
                        payload=payload,
                        rag_chunks=chunks,
                    )
                    analysis_text += "📚 **RAG KNOWLEDGE:**\n" + rag_advice
                    
                    advice_upper = rag_advice.upper()
                    if "CẢNH BÁO" in advice_upper or "WARNING" in advice_upper or "YẾU" in advice_upper or "CHỜ THÊM XÁC NHẬN" in advice_upper:
                        confidence -= 3
        except Exception as e:
            log.error(f"AIAnalyzer: RAG analysis error: {e}")
            analysis_text += f"Lỗi RAG: {e}"

    # ── Final Verdict ────────────────────────────────────────
    if confidence < 7:
        should_trade = False
        interactive_required = True

    # ── Persist to DB ────────────────────────────────────────
    try:
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        await database.insert_brief(
            symbols_scanned=1,
            scan_data=json.dumps([{"symbol": symbol, "source": "unified_pipeline"}]),
            ai_analysis=analysis_text,
            vision_data=json.dumps(vision_result),
            screenshot=str(screenshot_path) if screenshot_path else "",
            brief_text=f"[{event.action.upper()}] {symbol} @ {ts_str}\n\n{analysis_text}",
            success=1,
        )
    except Exception as db_err:
        log.warning(f"AIAnalyzer: Failed to persist capture to DB: {db_err}")

    # ── Telegram photo + caption ─────────────────────────────
    if screenshot_path and Path(screenshot_path).exists():
        formatted_vision = vision_module.format_vision_telegram(vision_result) if vision_result else "No Vision Data"
        caption = f"🥷 **AI ANALYSIS** — `{symbol}`\n\n{analysis_text[:800]}...\n\nScore: {confidence}/10"
        try:
            from notifier import send_telegram_photo as _send_photo
            import asyncio
            await asyncio.to_thread(_send_photo, Path(screenshot_path), caption=caption[:1024])
        except Exception as tg_err:
            log.warning(f"AIAnalyzer: Photo send failed: {tg_err}")
            await notifier.notify_all(caption)

    # ── Parse SL & TP ────────────────────────────────────────
    sl_val = event.sl
    tp_val = event.tp
    if not sl_val or not tp_val:
        sl_match = re.search(r"Stop\s*Loss:.*?(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)", analysis_text, re.IGNORECASE)
        tp_match = re.search(r"Take\s*Profit:.*?(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)", analysis_text, re.IGNORECASE)
        if sl_match and not sl_val: sl_val = sl_match.group(1).replace(",", "")
        if tp_match and not tp_val: tp_val = tp_match.group(1).replace(",", "")

    # Emit AnalysisComplete
    await _bus.emit(AnalysisComplete(
        signal_id=event.signal_id,
        symbol=event.symbol,
        action=event.action,
        price=event.price,
        quote_qty=event.quote_qty,
        sl=sl_val,
        tp=tp_val,
        confidence=confidence,
        analysis_text=analysis_text,
        screenshot_path=str(screenshot_path) if screenshot_path else "",
        should_trade=should_trade,
        interactive_required=interactive_required,
        vision_result=vision_result,
        exchange=getattr(event, 'exchange', 'binance'),
    ))

