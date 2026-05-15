"""
SignalProcessor — Deduplication, timeframe validation, and strategy routing.

Listens to: SignalReceived
Emits: SignalValidated | SignalRejected

Design Invariants:
- Dedup cache prevents duplicate signals within a TTL window.
- Circuit Breaker: Only 1H (60/1h/60m) timeframes are allowed for live trading.
- Stateless except for in-memory dedup cache.
"""
import logging
import time
from typing import Dict, Tuple

from core.event_bus import bus as _default_bus
from core.events import SignalReceived, SignalValidated, SignalRejected, AlertTriggered

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
# DEDUP CACHE
# ═══════════════════════════════════════════════════════════════

# In-memory dedup: key = (symbol, action), value = timestamp
_dedup_cache: Dict[Tuple[str, str], float] = {}
DEDUP_TTL_SEC = 60  # Ignore identical signals within 60s


def _is_duplicate(symbol: str, action: str) -> bool:
    """Check if this signal is a duplicate within the TTL window."""
    # BUG-04 fix: normalize both symbol AND action to upper/lower consistently
    # Using (upper, lower) to match how the key is built throughout the module
    key = (symbol.strip().upper(), action.strip().lower())
    now = time.time()
    last_seen = _dedup_cache.get(key, 0)
    if now - last_seen < DEDUP_TTL_SEC:
        return True
    _dedup_cache[key] = now
    return False


# ═══════════════════════════════════════════════════════════════
# TIMEFRAME VALIDATION (Circuit Breaker)
# ═══════════════════════════════════════════════════════════════

VALID_TRADE_INTERVALS = {"60", "1h", "60m"}


def _is_valid_trade_interval(interval: str) -> bool:
    """MIS v1 strategy only allows 1H timeframe for live trading."""
    return interval.strip().lower() in VALID_TRADE_INTERVALS


# ═══════════════════════════════════════════════════════════════
# EVENT HANDLER
# ═══════════════════════════════════════════════════════════════

@_default_bus.on(SignalReceived)
async def process_signal(event: SignalReceived) -> None:
    """
    Core signal processing logic:
    1. Skip dedup check for 'alert' actions (they go to AIAnalyzer directly).
    2. For 'buy'/'sell': validate timeframe, check dedup.
    3. Emit SignalValidated or SignalRejected accordingly.
    """
    action = event.action.lower()

    # Alert signals bypass trade validation — emit AlertTriggered for AIAnalyzer
    if action == "alert":
        log.info(f"SignalProcessor: Alert signal #{event.signal_id} for {event.symbol} — emitting AlertTriggered")
        await _bus.emit(AlertTriggered(
            signal_id=event.signal_id,
            symbol=event.symbol,
            price=str(event.price) if event.price else "",
            quote_qty=event.quote_qty,
            rag_advice=event.rag_advice,
            exchange=getattr(event, "exchange", "binance") or "binance",
        ))
        return

    # BUG-04 fix: normalize action before passing to _is_duplicate so key is consistent
    action = action.strip().lower()
    # ── Dedup Check ──────────────────────────────────────────
    if _is_duplicate(event.symbol, action):
        log.warning(f"SignalProcessor: Duplicate signal rejected — {action} {event.symbol}")
        await _bus.emit(SignalRejected(
            signal_id=event.signal_id,
            symbol=event.symbol,
            action=action,
            reason="duplicate_signal",
            exchange=event.exchange,
        ))
        return

    # ── Timeframe Circuit Breaker ────────────────────────────
    if action in ("buy", "sell"):
        if not _is_valid_trade_interval(event.interval):
            log.warning(
                f"SignalProcessor: Rejecting trade for {event.symbol}: "
                f"invalid interval '{event.interval}'. Only 1h/60 is allowed."
            )
            await _bus.emit(SignalRejected(
                signal_id=event.signal_id,
                symbol=event.symbol,
                action=action,
                reason="invalid_timeframe",
                interval=event.interval,
                exchange=event.exchange,
            ))
            return
    else:
        # Fallback for unknown actions
        log.warning(f"SignalProcessor: Unknown action '{action}' for {event.symbol}")
        await _bus.emit(SignalRejected(
            signal_id=event.signal_id,
            symbol=event.symbol,
            action=action,
            reason="unknown_action",
            exchange=event.exchange,
        ))
        return

    # ── Validated — emit downstream ──────────────────────────
    log.info(f"SignalProcessor: Signal #{event.signal_id} validated — {action} {event.symbol}")
    await _bus.emit(SignalValidated(
        signal_id=event.signal_id,
        symbol=event.symbol,
        action=action,
        price=event.price,
        quote_qty=event.quote_qty,
        sl=event.sl,
        tp=event.tp,
        exchange=event.exchange,
    ))


def reset_dedup_cache() -> None:
    """Clear dedup cache — for testing."""
    _dedup_cache.clear()
