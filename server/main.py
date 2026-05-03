import json
import logging
import time
import hmac
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Query, status, Body
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import aiohttp

import config
import notifier
import database
import rag

# ── P6 imports ───────────────────────────────────────────────────────────────
import mcp_client as _mcp_module
import watchlist as wl_module
import analysis as analysis_module
import brief as brief_module
import scheduler as scheduler_module

# ── P7 imports ───────────────────────────────────────────────────────────────
import telegram_bot as tg_bot_module
import vision as vision_module


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

STATIC_DIR = Path(__file__).parent / "static"


# ═══ LIFESPAN (startup/shutdown) ═════════════════════════════
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Khoi tao database, RAG Vector DB, MCP client va Scheduler khi server start."""
    await database.init_db()
    log.info("Database ready.")

    # ── RAG ───────────────────────────────────────────────────
    if config.RAG_ENABLED:
        log.info("RAG: Khởi tạo Vector DB từ Minervini Knowledge Base...")
        success = await rag.init_vector_db()
        if success:
            log.info("RAG: ✅ Vector DB sẵn sàng.")
        else:
            log.warning("RAG: ⚠️ Khởi tạo Vector DB thất bại. Server vẫn hoạt động bình thường.")
    else:
        log.info("RAG: Tính năng RAG đang TẮT (RAG_ENABLED=false).")

    # ── MCP (P6) ──────────────────────────────────────────────
    if config.MCP_ENABLED:
        mcp = _mcp_module.get_mcp_client()
        health = await mcp.health_check()
        if health.get("connected"):
            log.info("MCP: ✅ TradingView Desktop connected (CDP:9222).")
        else:
            log.warning(f"MCP: ⚠️ TradingView not connected — {health.get('error', 'unknown')}. Brief will retry at runtime.")
    else:
        log.info("MCP: Tính năng MCP đang TẮT (MCP_ENABLED=false).")

    # ── Scheduler (P6) ────────────────────────────────────────
    if config.BRIEF_ENABLED:
        scheduler_module.start_scheduler()
        log.info(f"Scheduler: ✅ Morning Brief scheduled at {config.BRIEF_CRON_TIME} ICT daily.")
    else:
        log.info("Scheduler: Morning Brief TẮT (BRIEF_ENABLED=false).")
    # ── Telegram Bot (P7) ────────────────────────────────────
    if config.TELEGRAM_BOT_ENABLED:
        tg_bot_module.start_bot()
        log.info("Telegram Bot: ✅ Interactive bot started (polling mode).")
    else:
        log.info("Telegram Bot: TẮT (TELEGRAM_BOT_ENABLED=false).")

    yield

    # ── Shutdown ──────────────────────────────────────────────
    tg_bot_module.stop_bot()
    scheduler_module.stop_scheduler()
    log.info("Server shutting down.")


app = FastAPI(
    title="TradingView Webhook Server",
    version="7.0",
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


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


# ═══ DASHBOARD ════════════════════════════════════════════════
@app.get("/dashboard")
async def dashboard():
    """Serve Performance Dashboard UI."""
    return FileResponse(str(STATIC_DIR / "dashboard.html"))


@app.get("/")
async def root():
    """Redirect to dashboard."""
    return FileResponse(str(STATIC_DIR / "dashboard.html"))


# ═══ HEALTH CHECK ═════════════════════════════════════════════
@app.get("/tv_health_check")
async def tv_health_check():
    return {
        "status": "ok",
        "service": "TradingView Webhook Server (FastAPI)",
        "version": "6.0",
        "rag_enabled": config.RAG_ENABLED,
        "mcp_enabled": config.MCP_ENABLED,
        "brief_enabled": config.BRIEF_ENABLED,
        "time": datetime.now(timezone.utc).isoformat(),
    }


# ═══ P6: MCP STATUS ═══════════════════════════════════════════
@app.get("/api/mcp/status")
async def mcp_status():
    """Kiểm tra kết nối TradingView Desktop qua CDP."""
    if not config.MCP_ENABLED:
        return {"enabled": False, "status": "disabled"}
    mcp = _mcp_module.get_mcp_client()
    health = await mcp.health_check()
    return {"enabled": True, **health}


# ═══ P6: WATCHLIST CRUD ═══════════════════════════════════════
@app.get("/api/watchlist")
async def get_watchlist_endpoint():
    """Lấy danh sách watchlist hiện tại."""
    symbols = wl_module.get_watchlist()
    return {"symbols": symbols, "count": len(symbols)}


@app.post("/api/watchlist")
async def add_watchlist_endpoint(body: dict = Body(...)):
    """Thêm symbol vào watchlist. Body: {\"symbol\": \"BTCUSDT\"}"""
    symbol = body.get("symbol", "").strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="'symbol' field required")
    return wl_module.add_symbol(symbol)


@app.delete("/api/watchlist/{symbol}")
async def remove_watchlist_endpoint(symbol: str):
    """Xóa symbol khỏi watchlist."""
    result = wl_module.remove_symbol(symbol)
    if not result["removed"]:
        raise HTTPException(status_code=404, detail=f"{symbol} not in watchlist")
    return result


@app.put("/api/watchlist/sync")
async def sync_watchlist_endpoint():
    """Sync watchlist từ TradingView Desktop (qua MCP)."""
    if not config.MCP_ENABLED:
        raise HTTPException(status_code=503, detail="MCP_ENABLED=false")
    mcp = _mcp_module.get_mcp_client()
    return await wl_module.sync_from_tradingview(mcp)


# ═══ P6: WATCHLIST SCAN ═══════════════════════════════════════
@app.get("/api/scan/watchlist")
async def scan_watchlist_endpoint(
    symbols: Optional[str] = Query(None, description="Comma-separated, e.g. BTCUSDT,ETHUSDT. Mặc định dùng watchlist."),
    timeframe: str = Query("D", description="Timeframe: D, W, 60..."),
):
    """Scan symbols theo Trend Template + VCP. Trả về kết quả đã sort."""
    if not config.MCP_ENABLED:
        raise HTTPException(status_code=503, detail="MCP_ENABLED=false")

    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()] if symbols else wl_module.get_watchlist()
    if not symbol_list:
        raise HTTPException(status_code=400, detail="Watchlist empty")

    mcp = _mcp_module.get_mcp_client()
    results = await analysis_module.scan_symbols(symbol_list, mcp)

    return {
        "scanned": len(results),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": [
            {
                "symbol": r.symbol,
                "price": r.price,
                "change_pct": r.change_pct,
                "trend_template_score": r.trend_template.score,
                "trend_template_stage": r.trend_template.stage,
                "trend_template_criteria": r.trend_template.criteria,
                "vcp_detected": r.vcp.detected,
                "volume_ratio": round(r.vcp.volume_ratio, 2),
                "range_ratio": round(r.vcp.range_ratio, 2),
                "pivot_level": r.vcp.pivot_level,
                "vcp_note": r.vcp.note,
                "error": r.error,
            }
            for r in results
        ],
    }


# ═══ P6: MORNING BRIEF ════════════════════════════════════════
@app.post("/api/brief/trigger")
async def trigger_brief_endpoint(background_tasks: BackgroundTasks):
    """Chạy Morning Brief ngay lập tức (non-blocking)."""
    background_tasks.add_task(brief_module.generate_morning_brief)
    return {"triggered": True, "message": "Morning Brief đang chạy... Kiểm tra Telegram trong 30-60 giây."}


@app.get("/api/brief/latest")
async def get_latest_brief_endpoint():
    """Lấy Morning Brief mới nhất đã generate."""
    brief = brief_module.get_latest_brief()
    if brief is None:
        return {"available": False, "message": "Chưa có brief nào. Dùng POST /api/brief/trigger để tạo."}
    return {"available": True, **brief}


# ═══ RAG TEST ENDPOINT ════════════════════════════════════════
@app.get("/api/rag/query")
async def rag_query_endpoint(
    q: str = Query(..., description="Câu truy vấn ngữ nghĩa (vd: 'Quy tắc VCP breakout')"),
    n: int = Query(3, ge=1, le=5, description="Số chunks trả về"),
):
    """
    Test endpoint để truy vấn Knowledge Base trực tiếp.
    Hữu ích để debug và verify RAG hoạt động đúng.
    """
    if not config.RAG_ENABLED:
        raise HTTPException(status_code=503, detail="RAG chưa được bật (RAG_ENABLED=false)")

    chunks = rag.query_knowledge(q, n_results=n)
    return {
        "query": q,
        "n_results": len(chunks),
        "chunks": [
            {
                "topic": c["metadata"].get("topic", ""),
                "chapter": c["metadata"].get("chunk_id", c["metadata"].get("filename", "")),
                "relevance": c["relevance_score"],
                "preview": c["content"][:300] + "..." if len(c["content"]) > 300 else c["content"],
            }
            for c in chunks
        ],
    }


@app.get("/api/rag/status")
async def rag_status_endpoint():
    """Kiểm tra trạng thái Vector DB."""
    if not config.RAG_ENABLED:
        return {"enabled": False, "status": "disabled"}

    collection = rag._collection
    if collection is None:
        return {"enabled": True, "status": "not_initialized", "count": 0}

    count = collection.count()
    return {
        "enabled": True,
        "status": "ready" if count > 0 else "empty",
        "vectors_count": count,
        "knowledge_dir": config.KNOWLEDGE_DIR,
        "chroma_db_path": config.CHROMA_DB_PATH,
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

    # ── RAG Analysis (chạy song song với trade execution) ─────────────
    rag_advice = ""
    if config.RAG_ENABLED and rag._collection is not None:
        try:
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
            log.error(f"RAG analysis error in webhook: {e}")
            rag_advice = ""

    # Dat lenh tren Binance neu Action la buy/sell
    if config.BINANCE_API_KEY and action in ("buy", "sell"):
        background_tasks.add_task(
            execute_trade_and_notify,
            signal_id=signal_id,
            action=action,
            symbol=symbol,
            price=price,
            quote_qty=quote_qty,
            rag_advice=rag_advice,
        )
        return {"received": True, "signal_id": signal_id, "status": "processing_async"}

    # Bao cao ngay neu chi nhan tin hieu
    await database.update_signal_status(signal_id, 1)

    msg = (
        f"📡 **Tín hiệu TradingView**\n"
        f"- Mã: `{symbol}`\n"
        f"- Hành động: `{action.upper()}`\n"
        f"- Giá: `{price}`\n"
        f"- Signal ID: `#{signal_id}`"
    )

    # Đính kèm phân tích RAG nếu có
    if rag_advice:
        msg += f"\n\n🧠 **Phân tích Minervini AI:**\n{rag_advice}"

    background_tasks.add_task(notifier.notify_all, msg)

    return {"received": True, "signal_id": signal_id, "order": None, "rag_enabled": bool(rag_advice)}


# ═══ BACKGROUND TRADE EXECUTION & NOTIFICATION ═══════════════
async def execute_trade_and_notify(
    signal_id: int, action: str, symbol: str, price: str, quote_qty: float,
    rag_advice: str = "",
):
    """Xu ly lenh bat dong bo va luu vao database."""
    try:
        result = await _place_binance_order_async(action, symbol, quote_qty)

        order_id = str(result.get("orderId", "N/A"))
        order_status = result.get("status", "FILLED")
        executed_qty = result.get("executedQty", "0")
        cummulative_quote = result.get("cummulativeQuoteQty", "0")

        exec_qty_float = float(executed_qty) if executed_qty else 0
        exec_price_float = (
            float(cummulative_quote) / exec_qty_float
            if exec_qty_float > 0
            else None
        )

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
        await database.update_signal_status(signal_id, 1)

        msg = (
            f"✅ **Lệnh Giao Dịch Thành Công**\n"
            f"- Cặp giao dịch: `{symbol}`\n"
            f"- Lệnh: `{action.upper()}`\n"
            f"- Giá kích hoạt TV: `{price}`\n"
            f"- Khối lượng yêu cầu: `{quote_qty}`\n"
            f"- Khối lượng khớp: `{executed_qty}`\n"
            f"- Tình trạng: `{order_status}`\n"
            f"- Order ID: `{order_id}`\n"
            f"- Signal ID: `#{signal_id}`"
        )

        if rag_advice:
            msg += f"\n\n🧠 **Phân tích Minervini AI:**\n{rag_advice}"

        log.info(f"Binance Order Success: {result}")
        await notifier.notify_all(msg)

    except Exception as e:
        error_msg = str(e)
        log.error(f"Trade Execution Failed: {error_msg}")

        await database.insert_trade(
            signal_id=signal_id,
            symbol=symbol,
            side=action.upper(),
            requested_qty=float(quote_qty),
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
    return await database.get_trades(
        symbol=symbol, limit=limit, offset=offset,
        from_date=from_date, to_date=to_date,
    )


# ═══ PERFORMANCE STATS ENDPOINT ═══════════════════════════════
@app.get("/trades/stats")
async def get_stats_endpoint(
    symbol: Optional[str] = Query(None, description="Filter theo cap giao dich"),
):
    """Tinh metrics hieu suat: Win Rate, Profit Factor, Drawdown."""
    return await database.get_stats(symbol=symbol)


# ═══ EQUITY CURVE ENDPOINT ════════════════════════════════════
@app.get("/trades/equity")
async def get_equity_endpoint(
    symbol: Optional[str] = Query(None, description="Filter theo cap giao dich"),
):
    """Tra ve equity curve data cho Chart.js."""
    return await database.get_equity_curve(symbol=symbol)


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


# ═══ VISION ENDPOINTS (P7) ═══════════════════════════════════════════

@app.post("/api/vision/analyze")
async def api_vision_analyze(symbol: str = Query(...), image_path: str = Query(...)):
    """Analyze a chart screenshot using Claude Vision API."""
    from pathlib import Path
    path = Path(image_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Image not found: {image_path}")

    result = await vision_module.analyze_chart_vision(
        image_path=path,
        symbol=symbol.upper(),
    )
    return result


if __name__ == "__main__":
    import uvicorn
    log.info(f"Starting FastAPI Webhook Server v7.0 on {config.HOST}:{config.PORT}")
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=config.DEBUG)
