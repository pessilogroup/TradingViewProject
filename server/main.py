import json
import logging
import time
import hmac
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Query, status
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import aiohttp

import config
import notifier
import database


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ═══ LIFESPAN (startup/shutdown) ═════════════════════════════
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Khoi tao database khi server start."""
    await database.init_db()
    log.info("Database ready.")
    yield
    log.info("Server shutting down.")


app = FastAPI(
    title="TradingView Webhook Server",
    version="3.0",
    lifespan=lifespan,
)


# ═══ MIDDLEWARE: IP WHITELISTING ══════════════════════════════
@app.middleware("http")
async def ip_whitelist_middleware(request: Request, call_next):
    if config.ENABLE_IP_WHITELIST:
        client_ip = request.client.host
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()

        if client_ip not in config.TV_WHITELIST_IPS and client_ip != "127.0.0.1":
            log.warning(f"Blocked request from unauthorized IP: {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"error": "IP not whitelisted"}
            )
    return await call_next(request)


# ═══ HEALTH CHECK ═════════════════════════════════════════════
@app.get("/tv_health_check")
async def tv_health_check():
    return {
        "status": "ok",
        "service": "TradingView Webhook Server (FastAPI)",
        "version": "3.0",
        "time": datetime.now(timezone.utc).isoformat(),
    }


# ═══ WEBHOOK ENDPOINT ═════════════════════════════════════════
@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Xac thuc bao mat
    secret = (
        request.headers.get("X-TV-Secret")
        or request.query_params.get("secret")
        or payload.pop("secret", None)
        or ""
    )

    if secret != config.WEBHOOK_SECRET:
        log.warning("Unauthorized webhook attempt (secret mismatch)")
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not payload:
        raise HTTPException(status_code=400, detail="Empty payload")

    action = payload.get("action", "").lower()
    symbol = payload.get("symbol", "")
    price = payload.get("price", "")
    ts = payload.get("time", "")
    quote_qty = payload.get("quoteQty", payload.get("size", 10))

    # Source IP
    source_ip = request.client.host
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        source_ip = forwarded.split(",")[0].strip()

    # Luu signal vao database
    try:
        price_float = float(price) if price else None
    except (ValueError, TypeError):
        price_float = None

    signal_id = await database.insert_signal(
        symbol=symbol,
        action=action,
        price=price_float,
        quote_qty=float(quote_qty) if quote_qty else None,
        source_ip=source_ip,
        payload=payload,
    )

    log.info(f"ALERT #{signal_id}  action={action}  symbol={symbol}  price={price}  qty={quote_qty}  time={ts}")

    # Dat lenh tren Binance neu Action la buy/sell
    if config.BINANCE_API_KEY and action in ("buy", "sell"):
        background_tasks.add_task(
            execute_trade_and_notify,
            signal_id=signal_id,
            action=action,
            symbol=symbol,
            price=price,
            quote_qty=quote_qty,
        )
        return {"received": True, "signal_id": signal_id, "status": "processing_async"}

    # Bao cao ngay neu chi nhan tin hieu
    await database.update_signal_status(signal_id, 1)  # processed = success
    msg = f"\U0001f4e1 **Tin hieu TradingView**\n- Ma: `{symbol}`\n- Hanh dong: `{action.upper()}`\n- Gia: `{price}`\n- Signal ID: `#{signal_id}`"
    background_tasks.add_task(notifier.notify_all, msg)

    return {"received": True, "signal_id": signal_id, "order": None}


# ═══ BACKGROUND TRADE EXECUTION & NOTIFICATION ═══════════════
async def execute_trade_and_notify(
    signal_id: int, action: str, symbol: str, price: str, quote_qty: float
):
    """Xu ly lenh bat dong bo va luu vao database."""
    try:
        result = await _place_binance_order_async(action, symbol, quote_qty)

        order_id = str(result.get("orderId", "N/A"))
        order_status = result.get("status", "FILLED")
        executed_qty = result.get("executedQty", "0")
        cummulative_quote = result.get("cummulativeQuoteQty", "0")

        # Tinh gia thuc te
        exec_qty_float = float(executed_qty) if executed_qty else 0
        exec_price_float = (
            float(cummulative_quote) / exec_qty_float
            if exec_qty_float > 0
            else None
        )

        # Luu vao database
        await database.insert_trade(
            signal_id=signal_id,
            symbol=symbol,
            side=action.upper(),
            order_id=order_id,
            status=order_status,
            requested_qty=float(quote_qty),
            executed_qty=exec_qty_float,
            executed_price=exec_price_float,
        )
        await database.update_signal_status(signal_id, 1)  # success

        msg = (
            f"\u2705 **Lenh Giao Dich Thanh Cong**\n"
            f"- Cap giao dich: `{symbol}`\n"
            f"- Lenh: `{action.upper()}`\n"
            f"- Gia kich hoat TV: `{price}`\n"
            f"- Khoi luong yeu cau: `{quote_qty}`\n"
            f"- Khoi luong khop: `{executed_qty}`\n"
            f"- Tinh trang: `{order_status}`\n"
            f"- Order ID: `{order_id}`\n"
            f"- Signal ID: `#{signal_id}`"
        )
        log.info(f"Binance Order Success: {result}")
        await notifier.notify_all(msg)

    except Exception as e:
        error_msg = str(e)
        log.error(f"Trade Execution Failed: {error_msg}")

        # Luu loi vao database
        await database.insert_trade(
            signal_id=signal_id,
            symbol=symbol,
            side=action.upper(),
            requested_qty=float(quote_qty),
            error_message=error_msg,
            status="FAILED",
        )
        await database.update_signal_status(signal_id, 2)  # failed

        msg = (
            f"\u274c **Loi Dat Lenh Binance**\n"
            f"- Ma: `{symbol}`\n"
            f"- Lenh: `{action.upper()}`\n"
            f"- Chi tiet loi: `{error_msg}`\n"
            f"- Signal ID: `#{signal_id}`"
        )
        await notifier.notify_all(msg)


# ═══ TRADE HISTORY ENDPOINT ═══════════════════════════════════
@app.get("/trades")
async def get_trades_endpoint(
    symbol: Optional[str] = Query(None, description="Filter theo cap giao dich"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    from_date: Optional[str] = Query(None, description="ISO format: 2026-01-01"),
    to_date: Optional[str] = Query(None, description="ISO format: 2026-12-31"),
):
    """Truy van lich su giao dich."""
    result = await database.get_trades(
        symbol=symbol, limit=limit, offset=offset,
        from_date=from_date, to_date=to_date,
    )
    return result


# ═══ PERFORMANCE STATS ENDPOINT ═══════════════════════════════
@app.get("/trades/stats")
async def get_stats_endpoint(
    symbol: Optional[str] = Query(None, description="Filter theo cap giao dich"),
):
    """Tinh metrics hieu suat: Win Rate, Profit Factor, Drawdown."""
    stats = await database.get_stats(symbol=symbol)
    return stats


# ═══ ASYNC BINANCE ORDER ═════════════════════════════════════
async def _place_binance_order_async(action: str, symbol: str, quote_qty: float) -> dict:
    """Async Binance market-order placement via aiohttp."""
    base = (
        "https://testnet.binance.vision"
        if config.BINANCE_TESTNET
        else "https://api.binance.com"
    )
    side = "BUY" if action == "buy" else "SELL"

    params = {
        "symbol": symbol.replace("/", "").upper(),
        "side": side,
        "type": "MARKET",
        "quoteOrderQty": quote_qty,
        "timestamp": int(time.time() * 1000),
    }

    query = "&".join(f"{k}={v}" for k, v in params.items())
    sig = hmac.new(
        config.BINANCE_API_SECRET.encode(), query.encode(), hashlib.sha256
    ).hexdigest()
    params["signature"] = sig

    headers = {"X-MBX-APIKEY": config.BINANCE_API_KEY}

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{base}/api/v3/order", params=params, headers=headers
        ) as resp:
            data = await resp.json()
            if resp.status != 200:
                raise Exception(f"Binance Error: {data}")
            return data


if __name__ == "__main__":
    import uvicorn
    log.info(f"Starting FastAPI Webhook Server v3.0 on {config.HOST}:{config.PORT}")
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=config.DEBUG)