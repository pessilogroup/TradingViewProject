"""
execution_server.py — Lightweight Execution Server for SERVER B (Execution Vault).

Receives pre-analyzed trade payloads from SERVER C via POST /api/execute-trade,
validates the X-Server-B-Secret header, executes trades via TradeEngine,
and returns results.

Runs on Tailscale VPN only (not exposed to WAN).
"""
import hmac
import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

# Ensure server/ is in path for imports
sys.path.insert(0, str(Path(__file__).parent))

import config
import database

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    await database.init_db()
    log.info("Execution Server started. Listening for trade commands.")
    yield
    log.info("Execution Server shutting down.")


app = FastAPI(
    title="TradingView Bot — Execution Server",
    description="SERVER B: Receives approved trades from SERVER C and executes on exchanges.",
    lifespan=lifespan,
)


def _validate_secret(request: Request) -> None:
    """Validate X-Server-B-Secret header using constant-time comparison."""
    expected = config.SERVER_B_SECRET
    if not expected:
        raise HTTPException(status_code=500, detail="SERVER_B_SECRET not configured")

    provided = request.headers.get("X-Server-B-Secret", "")
    if not hmac.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.post("/api/execute-trade")
async def execute_trade(request: Request):
    """Execute a pre-analyzed trade from SERVER C."""
    _validate_secret(request)

    body = await request.json()

    # Validate required fields
    symbol = body.get("symbol")
    action = body.get("action")
    price = body.get("price")

    if not symbol or not action:
        raise HTTPException(status_code=400, detail="Missing required fields: symbol, action")

    # Extract trade parameters safely
    def safe_float(val, default=None):
        if val is None or val == "":
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    qty = safe_float(body.get("qty"))
    price = safe_float(body.get("price"))
    quote_qty = safe_float(body.get("quote_qty"))

    if quote_qty is None and qty is not None and price is not None:
        quote_qty = qty * price

    if quote_qty is None:
        quote_qty = 10.0

    sl = body.get("sl", "")
    tp = body.get("tp", "")
    exchange = body.get("exchange", config.DEFAULT_EXCHANGE)
    analysis_text = body.get("analysis_text") or body.get("analysis", "")

    try:
        # Import and use TradeEngine's event-based execution
        from core.event_bus import EventBus
        from core.events import TradeApproved, TradeExecuted, TradeFailed

        # Create isolated event bus for this execution
        exec_bus = EventBus()

        # Store result via event handler
        result_holder = {}

        @exec_bus.on(TradeExecuted)
        async def on_executed(event: TradeExecuted):
            result_holder["success"] = True
            result_holder["order_id"] = event.order_id
            result_holder["fill_price"] = event.executed_price
            result_holder["status"] = event.status
            result_holder["executed_qty"] = event.executed_qty

        @exec_bus.on(TradeFailed)
        async def on_failed(event: TradeFailed):
            result_holder["success"] = False
            result_holder["error"] = event.error

        # Save signal to DB first
        signal_id = await database.insert_signal(
            symbol=symbol,
            action=action,
            price=price,
            quote_qty=quote_qty,
            source_ip=request.client.host if request.client else "0.0.0.0",
            payload=body,
        )

        # Import trade engine and override its bus
        from engine import trade_engine
        original_bus = trade_engine.get_bus()
        trade_engine.set_bus(exec_bus)

        try:
            # Create and process TradeApproved event
            approved = TradeApproved(
                signal_id=signal_id,
                symbol=symbol,
                action=action,
                price=price,
                quote_qty=quote_qty,
                sl=str(sl),
                tp=str(tp),
                exchange=exchange,
                approved_by="ServerC-Analyzer",
                analysis_text=analysis_text,
            )

            await trade_engine.execute_trade(approved)
        finally:
            trade_engine.set_bus(original_bus)

        if result_holder.get("success"):
            # Send Telegram notification
            try:
                from notifier import notify_all
                msg = (
                    f"✅ **Pipeline Trade Executed on {config.EXECUTION_TARGET_NAME}**\n"
                    f"- Symbol: `{symbol}`\n"
                    f"- Action: `{action.upper()}`\n"
                    f"- Order ID: `{result_holder.get('order_id', 'N/A')}`\n"
                    f"- Fill Price: `{result_holder.get('fill_price', 'N/A')}`\n"
                    f"- Status: `{result_holder.get('status', 'N/A')}`"
                )
                await notify_all(msg)
            except Exception as e:
                log.warning(f"Telegram notification failed: {e}")

            return JSONResponse({
                "success": True,
                "order_id": result_holder.get("order_id"),
                "fill_price": result_holder.get("fill_price"),
                "status": result_holder.get("status"),
                "executed_qty": result_holder.get("executed_qty"),
            })
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": result_holder.get("error", "Trade execution failed"),
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        log.exception(f"Execute trade error: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.get("/health")
async def health():
    return {"status": "ok", "server": "execution-vault-b"}
