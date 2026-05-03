import json
import logging
import time
import hmac
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, status
from fastapi.responses import JSONResponse
import aiohttp

import config
import notifier

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

app = FastAPI(title="TradingView Webhook Server", version="2.0")

# ─── MIDDLEWARE: IP WHITELISTING ──────────────────────────────────────────────
@app.middleware("http")
async def ip_whitelist_middleware(request: Request, call_next):
    if config.ENABLE_IP_WHITELIST:
        # TradingView IPs
        client_ip = request.client.host
        # Also check x-forwarded-for if behind a proxy like Cloudflare
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

# ─── HEALTH CHECK ─────────────────────────────────────────────────────────────
@app.get("/tv_health_check")
async def tv_health_check():
    return {
        "status": "ok",
        "service": "TradingView Webhook Server (FastAPI)",
        "time": datetime.now(timezone.utc).isoformat(),
    }

# ─── WEBHOOK ENDPOINT ─────────────────────────────────────────────────────────
@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Xác thực bảo mật
    secret = (
        request.headers.get("X-TV-Secret")
        or request.query_params.get("secret")
        or payload.pop("secret", None)
        or ""
    )
    
    if secret != config.WEBHOOK_SECRET:
        log.warning(f"Unauthorized webhook attempt (secret mismatch)")
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not payload:
        raise HTTPException(status_code=400, detail="Empty payload")

    action = payload.get("action", "").lower()
    symbol = payload.get("symbol", "")
    price  = payload.get("price", "")
    ts     = payload.get("time", "")
    
    # Kích thước lệnh (Order Sizing) - lấy từ TradingView hoặc mặc định 10
    quote_qty = payload.get("quoteQty", payload.get("size", 10))

    log.info(f"ALERT  action={action}  symbol={symbol}  price={price}  qty={quote_qty}  time={ts}")

    # Đặt lệnh trên Binance nếu Action là buy/sell
    if config.BINANCE_API_KEY and action in ("buy", "sell"):
        background_tasks.add_task(
            execute_trade_and_notify, 
            action=action, 
            symbol=symbol, 
            price=price, 
            quote_qty=quote_qty
        )
        return {"received": True, "status": "processing_async"}

    # Báo cáo ngay lập tức nếu chỉ nhận tín hiệu mà không Trade
    msg = f"🔔 **Tín hiệu TradingView**\n- Mã: `{symbol}`\n- Hành động: `{action.upper()}`\n- Giá: `{price}`"
    background_tasks.add_task(notifier.notify_all, msg)

    return {"received": True, "order": None}


# ─── BACKGROUND TRADE EXECUTION & NOTIFICATION ────────────────────────────────
async def execute_trade_and_notify(action: str, symbol: str, price: str, quote_qty: float):
    """Xử lý lệnh bất đồng bộ để không treo Webhook và báo cáo qua Telegram"""
    try:
        result = await _place_binance_order_async(action, symbol, quote_qty)
        
        # Format tin nhắn thành công
        order_id = result.get('orderId', 'N/A')
        status = result.get('status', 'FILLED')
        executed_qty = result.get('executedQty', 'N/A')
        
        msg = (
            f"✅ **Lệnh Giao Dịch Thành Công**\n"
            f"- Cặp giao dịch: `{symbol}`\n"
            f"- Lệnh: `{action.upper()}`\n"
            f"- Giá kích hoạt TV: `{price}`\n"
            f"- Khối lượng yêu cầu: `{quote_qty}`\n"
            f"- Khối lượng khớp: `{executed_qty}`\n"
            f"- Tình trạng: `{status}`\n"
            f"- Order ID: `{order_id}`"
        )
        log.info(f"Binance Order Success: {result}")
        await notifier.notify_all(msg)
        
    except Exception as e:
        error_msg = str(e)
        log.error(f"Trade Execution Failed: {error_msg}")
        msg = (
            f"❌ **Lỗi Đặt Lệnh Binance**\n"
            f"- Mã: `{symbol}`\n"
            f"- Lệnh: `{action.upper()}`\n"
            f"- Chi tiết lỗi: `{error_msg}`"
        )
        await notifier.notify_all(msg)


# ─── ASYNC BINANCE ORDER ──────────────────────────────────────────────────────
async def _place_binance_order_async(action: str, symbol: str, quote_qty: float) -> dict:
    """Async Binance market-order placement via aiohttp."""
    base = "https://testnet.binance.vision" if config.BINANCE_TESTNET else "https://api.binance.com"
    side = "BUY" if action == "buy" else "SELL"
    
    params = {
        "symbol": symbol.replace("/", "").upper(),
        "side": side,
        "type": "MARKET",
        "quoteOrderQty": quote_qty,
        "timestamp": int(time.time() * 1000),
    }
    
    query = "&".join(f"{k}={v}" for k, v in params.items())
    sig = hmac.new(config.BINANCE_API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    params["signature"] = sig
    
    headers = {"X-MBX-APIKEY": config.BINANCE_API_KEY}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{base}/api/v3/order", params=params, headers=headers) as resp:
            data = await resp.json()
            if resp.status != 200:
                raise Exception(f"Binance Error: {data}")
            return data

if __name__ == "__main__":
    import uvicorn
    log.info(f"Starting FastAPI Webhook Server on {config.HOST}:{config.PORT}")
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=config.DEBUG)
