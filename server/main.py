import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
import secrets

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Query, status, Body
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

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
import binance_client as binance_module


# ── Fix Windows cp1252 UnicodeEncodeError for emoji in log messages ──────────
import sys, io
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Setup logging — StreamHandler explicitly UTF-8 to avoid cp1252 crash on Windows
_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)s  %(message)s"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
        _stream_handler,
    ],
)
log = logging.getLogger(__name__)


STATIC_DIR = Path(__file__).parent / "static"

# ── Stealth Capture Cooldown ──
LAST_CAPTURE_TIME = {}
CAPTURE_COOLDOWN_SEC = 300  # Giới hạn 5 phút mỗi mã (chống spam Webhook)
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
    version="7.6",
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


# ═══ DASHBOARD AUTH MIDDLEWARE ════════════════════════════════
@app.middleware("http")
async def dashboard_auth_middleware(request: Request, call_next):
    """Simple bearer-token auth for /api/* endpoints (skip /webhook, /tv_health_check, static, dashboard HTML)."""
    path = request.url.path
    # Skip auth for: webhook, health check, static files, dashboard HTML, root
    skip_paths = ("/webhook", "/tv_health_check", "/health", "/static", "/dashboard", "/")
    if not config.DASHBOARD_TOKEN or path in skip_paths or path.startswith("/static"):
        return await call_next(request)

    if path.startswith("/api/") or path.startswith("/trades"):
        auth_header = request.headers.get("Authorization", "")
        token_param = request.query_params.get("token", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        elif token_param:
            token = token_param

        if not secrets.compare_digest(token, config.DASHBOARD_TOKEN):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Invalid or missing token"},
            )
    return await call_next(request)


# ═══ HEALTH CHECK (Sprint 7.3) ════════════════════════════════
@app.get("/health")
async def health_check():
    """Docker/K8s health probe — unauthenticated, lightweight."""
    import time as _t
    uptime_s = int(_t.time() - config.SERVER_START_TIME)
    hours, remainder = divmod(uptime_s, 3600)
    minutes, seconds = divmod(remainder, 60)

    status_data = {
        "status": "healthy",
        "version": "7.3",
        "uptime": f"{hours}h {minutes}m {seconds}s",
        "uptime_seconds": uptime_s,
    }

    # DB check
    try:
        import aiosqlite
        async with aiosqlite.connect(config.DB_PATH) as db:
            await db.execute("SELECT 1")
        status_data["database"] = "ok"
    except Exception as e:
        status_data["database"] = f"error: {e}"
        status_data["status"] = "degraded"

    # Binance client mode
    status_data["binance"] = {
        "dry_run": config.BINANCE_DRY_RUN,
        "testnet": config.BINANCE_TESTNET,
    }

    # Feature flags
    status_data["features"] = {
        "rag": config.RAG_ENABLED,
        "mcp": config.MCP_ENABLED,
        "brief": config.BRIEF_ENABLED,
        "telegram_bot": config.TELEGRAM_BOT_ENABLED,
    }

    return status_data


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
                "vol_breakout": getattr(r.vcp, "vol_breakout", False),
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

    # Allow dashboard users (authenticated via DASHBOARD_TOKEN) to bypass webhook secret
    dashboard_auth = request.headers.get("Authorization", "")
    is_dashboard_user = (
        config.DASHBOARD_TOKEN
        and dashboard_auth.startswith("Bearer ")
        and secrets.compare_digest(dashboard_auth[7:], config.DASHBOARD_TOKEN)
    )

    if not is_dashboard_user and secret != config.WEBHOOK_SECRET:
        log.warning("Unauthorized webhook attempt (secret mismatch)")
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not payload:
        raise HTTPException(status_code=400, detail="Empty payload")

    action = payload.get("action", "").lower()
    symbol = payload.get("symbol", "")
    price = payload.get("price", "")
    ts = payload.get("time", "")
    quote_qty = payload.get("quoteQty", payload.get("size", 10))
    interval = str(payload.get("interval", "")).strip().lower()
    
    sl_str = payload.get("sl", "")
    tp_str = payload.get("tp", "")

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

    # ── Autonomous AI Analyst (Stealth Capture) cho Action = "alert" ──────────
    if action == "alert" and config.MCP_ENABLED:
        now = datetime.now(timezone.utc).timestamp()
        last_time = LAST_CAPTURE_TIME.get(symbol, 0)
        
        if now - last_time < CAPTURE_COOLDOWN_SEC:
            log.warning(f"Cooldown active for {symbol}. Skipping Stealth Capture.")
        else:
            LAST_CAPTURE_TIME[symbol] = now
            background_tasks.add_task(
                process_alert_stealth_capture,
                signal_id=signal_id,
                symbol=symbol,
                price=price,
                quote_qty=quote_qty,
                rag_advice=rag_advice
            )
            return {"received": True, "signal_id": signal_id, "status": "stealth_capture_async"}

    # ── Đặt lệnh trực tiếp nếu Action = "buy" / "sell" (Pine Script cũ) ───────
    if (config.BINANCE_API_KEY or config.BINANCE_DRY_RUN) and action in ("buy", "sell"):
        # --- TIMEFRAME FILTER (CIRCUIT BREAKER) ---
        valid_intervals = ["60", "1h", "60m"]
        if interval not in valid_intervals:
            log.warning(f"Rejecting trade for {symbol}: invalid interval '{interval}'. Only 1h/60 is allowed.")
            await database.update_signal_status(signal_id, 2) # 2 = FAILED/REJECTED
            msg = (
                f"⛔ **Lệnh Bị Từ Chối (Timeframe Filter)**\n"
                f"- Mã: `{symbol}`\n"
                f"- Hành động: `{action.upper()}`\n"
                f"- Lỗi: `Phát hiện khung thời gian '{interval}'. Chiến lược MIS v1 chỉ được phép chạy trên khung 1H (60).`\n"
                f"- Signal ID: `#{signal_id}`"
            )
            background_tasks.add_task(notifier.notify_all, msg)
            return {"received": True, "signal_id": signal_id, "status": "rejected", "reason": "invalid_timeframe"}

        background_tasks.add_task(
            execute_trade_and_notify,
            signal_id=signal_id,
            action=action,
            symbol=symbol,
            price=price,
            quote_qty=quote_qty,
            sl=sl_str,
            tp=tp_str,
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


# ── STEALTH CAPTURE & AUTONOMOUS AI ANALYST ─────────────────────────
import re

async def process_alert_stealth_capture(
    signal_id: int, symbol: str, price: str, quote_qty: float, rag_advice: str = ""
):
    """
    Xử lý tín hiệu 'alert' từ Webhook:
    1. Chụp màn hình TradingView ẩn danh (active_only).
    2. Chạy Vision AI phân tích Hành vi + SL/TP.
    3. Đặt lệnh nếu điểm >= 7.
    """
    log.info(f"Stealth capture triggered for {symbol}")
    await notifier.notify_all(f"🤖 **Stealth Capture:** Đang chụp ảnh và phân tích `{symbol}`...")

    try:
        from mcp_client import get_mcp_client
        mcp = get_mcp_client()
        health = await mcp.health_check()
        if not health.get("connected"):
            await notifier.notify_all(f"⚠️ **Stealth Capture:** TradingView MCP chưa kết nối.")
            return

        # ── Screenshot với tên file cụ thể để truy vết ──────────────────
        from datetime import datetime as _dt
        ts_str = _dt.now().strftime("%Y%m%d_%H%M%S")
        save_path = Path(__file__).parent / "screenshots" / f"stealth_{symbol}_{ts_str}.png"

        screenshot_path = await mcp.capture_screenshot(
            symbol="active",
            timeframe="active",
            region="chart",
            save_path=save_path,
            active_only=True,
            crop=True,  # Crop chart area only
        )

        if not screenshot_path or not Path(screenshot_path).exists():
            await notifier.notify_all(f"⚠️ **Stealth Capture:** Lỗi chụp ảnh biểu đồ.")
            return

        # ── Vision AI Analysis ───────────────────────────────────────────
        result = await vision_module.analyze_chart_vision(
            image_path=Path(screenshot_path),
            symbol=symbol,
        )

        if result.get("error"):
            await notifier.notify_all(f"❌ **Stealth Capture Error:** {result['error']}")
            return

        analysis_text = result.get("analysis", "")
        confidence = result.get("confidence", 0)

        # ── Persist Vision Result to DB ──────────────────────────────────
        import json as _json
        try:
            await database.insert_brief(
                symbols_scanned=1,
                scan_data=_json.dumps([{"symbol": symbol, "source": "stealth_capture"}]),
                ai_analysis=analysis_text,
                vision_data=_json.dumps(result),
                screenshot=str(screenshot_path),
                brief_text=f"[Stealth Capture] {symbol} @ {ts_str}\n\n{analysis_text}",
                success=1,
            )
            log.info(f"Stealth capture vision result saved to DB for {symbol}")
        except Exception as db_err:
            log.warning(f"Failed to persist stealth capture to DB: {db_err}")

        # Parse SL & TP bằng Regex
        sl_match = re.search(r"Stop\s*Loss:.*?(\d+(?:\.\d+)?)", analysis_text, re.IGNORECASE)
        tp_match = re.search(r"Take\s*Profit:.*?(\d+(?:\.\d+)?)", analysis_text, re.IGNORECASE)
        sl_val = sl_match.group(1) if sl_match else ""
        tp_val = tp_match.group(1) if tp_match else ""

        # ── Format & Send Telegram (photo + caption) ─────────────────────
        formatted_vision = vision_module.format_vision_telegram(result)
        caption = f"🥷 **STEALTH CAPTURE** — `{symbol}`\n\n{formatted_vision}"

        if confidence >= 7:
            caption += f"\n\n⚡ Điểm đủ chuẩn (≥7). Tiến hành đặt lệnh..."

        # Gửi ảnh chart kèm phân tích
        try:
            from notifier import send_telegram_photo as _send_photo
            import asyncio as _aio
            await _aio.to_thread(_send_photo, Path(screenshot_path), caption=caption[:1024])
            if len(caption) > 1024:
                await notifier.notify_all(caption)
        except Exception as tg_err:
            log.warning(f"Photo send failed, falling back to text: {tg_err}")
            await notifier.notify_all(caption)

        if confidence >= 7:
            await execute_trade_and_notify(
                signal_id=signal_id,
                action="buy",
                symbol=symbol,
                price=price,
                quote_qty=quote_qty,
                sl=sl_val,
                tp=tp_val,
                rag_advice=rag_advice,
                combined_score=result.get("combined_score"),
            )
        else:
            await notifier.notify_all(
                f"🛑 Lệnh `{symbol}` bị từ chối — điểm ({confidence}/10) không đủ chuẩn SEPA."
            )

    except Exception as e:
        log.error(f"Stealth capture process error: {e}", exc_info=True)
        await notifier.notify_all(f"❌ **Stealth Capture Failed:** {str(e)}")



# ═══ BACKGROUND TRADE EXECUTION & NOTIFICATION (Sprint 7.2) ══
async def execute_trade_and_notify(
    signal_id: int, action: str, symbol: str, price: str, quote_qty: float,
    sl: str = "", tp: str = "", rag_advice: str = "",
    combined_score: str = None,
):
    """Smart order execution: MARKET entry + OCO exit with risk management."""
    client = binance_module.get_client()
    try:
        entry_price = float(price) if price else 0.0
    except (ValueError, TypeError):
        entry_price = 0.0

    try:
        sl_price = float(sl) if sl else None
    except (ValueError, TypeError):
        sl_price = None

    try:
        tp_price = float(tp) if tp else None
    except (ValueError, TypeError):
        tp_price = None

    try:
        # Execute smart order (MARKET + OCO)
        result = client.execute_smart_order(
            symbol=symbol,
            side=action.upper(),
            entry_price=entry_price,
            quote_qty=quote_qty if quote_qty else None,
            sl_price=sl_price,
            tp_price=tp_price,
        )
        # Await the coroutine
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
                combined_score=combined_score,
            )

            # Update with OCO details
            if result.risk:
                await database.update_trade_oco(
                    trade_id=trade_id,
                    stop_loss_price=result.risk.stop_loss_price,
                    take_profit_price=result.risk.take_profit_price,
                    oco_order_id=oco_id,
                    order_type=order_type,
                )

            await database.update_signal_status(signal_id, 1)

            # Telegram notification
            msg = binance_module.format_order_telegram(result)
            if rag_advice:
                msg += f"\n\n🧠 **Phân tích Minervini AI:**\n{rag_advice}"

            log.info(f"Smart Order Success: {order_id} (type={order_type})")
            await notifier.notify_all(msg)

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
            combined_score=combined_score,
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


# ═══ BINANCE ACCOUNT ENDPOINT (Sprint 7.2) ═══════════════════

@app.get("/api/binance/account")
async def binance_account_endpoint(
    asset: str = Query("USDT", description="Asset to check balance"),
):
    """Get Binance account balance."""
    client = binance_module.get_client()
    balance = await client.get_account_balance(asset)
    return {
        "asset": asset.upper(),
        "balance": balance,
        "dry_run": client.dry_run,
        "testnet": client.testnet,
    }


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


# ═══ BRIEFS ENDPOINTS (P7.6) ═════════════════════════════════════════

@app.get("/api/briefs")
async def get_briefs_endpoint(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List historical morning briefs with pagination."""
    return await database.get_briefs(limit=limit, offset=offset)


@app.get("/api/briefs/{brief_id}")
async def get_brief_detail_endpoint(brief_id: int):
    """Get a specific brief by ID."""
    brief = await database.get_brief_by_id(brief_id)
    if brief is None:
        raise HTTPException(status_code=404, detail=f"Brief #{brief_id} not found")
    return brief


@app.get("/api/vision/history")
async def get_vision_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List vision analysis history (Stealth Captures + Morning Briefs with vision data).
    Returns items with screenshot path, ai_analysis, vision_data JSON.
    """
    import json as _json
    data = await database.get_briefs(limit=limit, offset=offset)
    items = data.get("briefs", [])

    result = []
    for b in items:
        vision_data = {}
        if b.get("vision_data"):
            try:
                vision_data = _json.loads(b["vision_data"])
            except Exception:
                pass

        screenshot = b.get("screenshot", "")
        # Determine if screenshot is accessible (serve from /api/vision/screenshot/<id>)
        result.append({
            "id": b["id"],
            "created_at": b["created_at"],
            "symbol": vision_data.get("symbol", "—"),
            "ai_analysis": b.get("ai_analysis", ""),
            "confidence": vision_data.get("confidence", 0),
            "patterns": vision_data.get("patterns", []),
            "combined_score": vision_data.get("combined_score", "—"),
            "verdict": vision_data.get("verdict", ""),
            "has_screenshot": bool(screenshot),
            "screenshot_url": f"/api/vision/screenshot/{b['id']}" if screenshot else None,
            "source": "stealth" if "[Stealth Capture]" in (b.get("brief_text") or "") else "morning_brief",
        })
    return {"items": result, "total": data.get("total", 0)}


@app.get("/api/vision/screenshot/{brief_id}")
async def get_vision_screenshot(brief_id: int):
    """Serve screenshot image for a vision analysis entry."""
    from fastapi.responses import FileResponse
    brief = await database.get_brief_by_id(brief_id)
    if not brief or not brief.get("screenshot"):
        raise HTTPException(status_code=404, detail="No screenshot for this brief")
    img_path = Path(brief["screenshot"])
    if not img_path.exists():
        raise HTTPException(status_code=404, detail=f"Screenshot file not found: {img_path}")
    return FileResponse(img_path, media_type="image/png")


# ═══ SYSTEM STATUS (P7.6) ════════════════════════════════════════════

@app.get("/api/system/status")
async def system_status_endpoint():
    """Aggregated system status for dashboard."""
    import time as _time

    # MCP status
    mcp_status = {"enabled": False, "connected": False}
    if config.MCP_ENABLED:
        try:
            mcp = _mcp_module.get_mcp_client()
            health = await mcp.health_check()
            mcp_status = {"enabled": True, "connected": health.get("connected", False)}
        except Exception:
            mcp_status = {"enabled": True, "connected": False}

    # RAG status
    rag_status = {"enabled": False, "vectors_count": 0}
    if config.RAG_ENABLED:
        try:
            collection = rag._collection
            count = collection.count() if collection else 0
            rag_status = {"enabled": True, "vectors_count": count}
        except Exception:
            rag_status = {"enabled": True, "vectors_count": 0}

    # DB counts
    try:
        db_counts = await database.get_db_counts()
    except Exception:
        db_counts = {"signals_count": 0, "trades_count": 0, "briefs_count": 0}

    # Latest brief
    latest_brief = brief_module.get_latest_brief()
    last_brief_time = latest_brief.get("timestamp") if latest_brief else None

    # Uptime
    uptime_seconds = int(_time.time() - config.SERVER_START_TIME)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}h {minutes}m {seconds}s"

    return {
        "server": {
            "version": "7.6",
            "uptime": uptime_str,
            "uptime_seconds": uptime_seconds,
            "time": datetime.now(timezone.utc).isoformat(),
        },
        "mcp": mcp_status,
        "scheduler": {
            "enabled": config.BRIEF_ENABLED,
            "cron_time": config.BRIEF_CRON_TIME,
            "last_brief": last_brief_time,
        },
        "rag": rag_status,
        "telegram_bot": {
            "enabled": config.TELEGRAM_BOT_ENABLED,
        },
        "database": db_counts,
        "auth_required": bool(config.DASHBOARD_TOKEN),
    }


# ═══ SCAN TRIGGER (P7.6) ═════════════════════════════════════════════

@app.post("/api/scan/trigger")
async def trigger_scan_endpoint(
    background_tasks: BackgroundTasks,
    timeframe: str = Query("D", description="Timeframe: D, W, 60..."),
):
    """Run an on-demand watchlist scan."""
    if not config.MCP_ENABLED:
        raise HTTPException(status_code=503, detail="MCP_ENABLED=false")

    symbol_list = wl_module.get_watchlist()
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
                "vol_breakout": getattr(r.vcp, "vol_breakout", False),
                "volume_ratio": round(r.vcp.volume_ratio, 2),
                "range_ratio": round(r.vcp.range_ratio, 2),
                "pivot_level": r.vcp.pivot_level,
                "vcp_note": r.vcp.note,
                "error": r.error,
            }
            for r in results
        ],
    }


if __name__ == "__main__":
    import uvicorn
    log.info(f"Starting FastAPI Webhook Server v7.6 on {config.HOST}:{config.PORT}")
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=config.DEBUG)
