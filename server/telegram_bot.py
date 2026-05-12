"""
P7 Sprint 7.4+7.2 — Telegram Bot Interactive
Chuyển từ push-only notification → interactive bot với commands.

Commands:
    /start      - Giới thiệu bot
    /help       - Danh sách commands
    /status     - Server + MCP + Scheduler status
    /brief      - Chạy Morning Brief ngay
    /scan       - Scan watchlist (Trend Template + VCP)
    /vision SYM - AI Vision phân tích chart screenshot
    /grade      - AI Mentor chấm điểm trade (bảo toàn Bar Replay)
    /watchlist  - Xem watchlist hiện tại
    /add SYM    - Thêm symbol vào watchlist
    /remove SYM - Xóa symbol khỏi watchlist
    /balance    - Xem Binance account balance

Kiến trúc:
    Bot chạy trong background thread (polling) song song với FastAPI.
    Bot gọi trực tiếp vào các module: watchlist, analysis, brief, mcp_client.
"""

import logging
import asyncio
import threading
from datetime import datetime

log = logging.getLogger(__name__)

# Lazy imports — only load if bot is enabled
_bot_app = None
_bot_thread = None


def _get_imports():
    """Lazy import python-telegram-bot to avoid crash if not installed."""
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        ApplicationBuilder,
        CommandHandler,
        CallbackQueryHandler,
        ContextTypes,
    )
    return Update, InlineKeyboardButton, InlineKeyboardMarkup, \
           ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes


# ── Command Handlers ──────────────────────────────────────────────────────

async def cmd_start(update, context):
    """Giới thiệu bot."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = [
        [
            InlineKeyboardButton("📊 Scan Watchlist", callback_data="scan"),
            InlineKeyboardButton("🌅 Morning Brief", callback_data="brief"),
        ],
        [
            InlineKeyboardButton("📋 Watchlist", callback_data="watchlist"),
            InlineKeyboardButton("🔧 Status", callback_data="status"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🤖 *Minervini AI Trading Bot v7.0*\n\n"
        "Tôi là bot giao dịch dựa trên chiến lược *SEPA* của Mark Minervini.\n\n"
        "🧠 *Khả năng:*\n"
        "• Scan watchlist — Trend Template (8 criteria) + VCP\n"
        "• Morning Brief tự động 07:00 ICT\n"
        "• RAG AI phân tích dựa trên sách Minervini\n"
        "• 👁️ AI Vision — Claude nhìn chart nhận diện pattern\n"
        "• Screenshot chart qua TradingView MCP\n\n"
        "Dùng /help để xem commands hoặc chọn bên dưới:",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


async def cmd_help(update, context):
    """Danh sách commands."""
    await update.message.reply_text(
        "📖 *Commands:*\n\n"
        "/status — Server + MCP + Scheduler status\n"
        "/brief — Chạy Morning Brief ngay\n"
        "/scan — Scan watchlist (TT + VCP)\n"
        "/vision `SYMBOL` — 👁️ AI Vision phân tích chart\n"
        "/grade — 👨‍🏫 AI Mentor chấm điểm trade (Bar Replay)\n"
        "/watchlist — Xem danh sách symbols\n"
        "/add `SYMBOL` — Thêm symbol (VD: /add FPT)\n"
        "/remove `SYMBOL` — Xóa symbol (VD: /remove SOLUSDT)\n"
        "/balance — 💰 Xem Binance account balance\n"
        "/help — Hiện menu này",
        parse_mode="Markdown",
    )


async def cmd_status(update, context):
    """Trạng thái hệ thống."""
    import config

    # Server info
    lines = [
        "🔧 *System Status*\n",
        f"⏰ Server time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        f"🌐 Server: FastAPI v7.0 on :{config.PORT}",
    ]

    # RAG status
    rag_status = "✅ Enabled" if config.RAG_ENABLED and config.ANTHROPIC_API_KEY else "❌ Disabled"
    lines.append(f"🧠 RAG: {rag_status}")

    # MCP status
    if config.MCP_ENABLED:
        try:
            from mcp_client import get_mcp_client
            mcp = get_mcp_client()
            health = await mcp.health_check()
            mcp_status = "✅ Connected" if health.get("connected") else "⚠️ Not connected"
        except Exception:
            mcp_status = "⚠️ Error"
    else:
        mcp_status = "❌ Disabled"
    lines.append(f"🖥️ MCP (CDP:{config.MCP_CDP_PORT}): {mcp_status}")

    # Scheduler status
    brief_status = "✅ Active" if config.BRIEF_ENABLED else "❌ Disabled"
    lines.append(f"⏰ Brief Scheduler: {brief_status} ({config.BRIEF_CRON_TIME} ICT)")

    # Telegram
    tg_status = "✅ Connected" if config.TELEGRAM_BOT_TOKEN else "❌ No token"
    lines.append(f"📱 Telegram: {tg_status}")

    # Watchlist
    try:
        from watchlist import get_watchlist
        wl = get_watchlist()
        lines.append(f"📋 Watchlist: {len(wl)} symbols")
    except Exception:
        lines.append("📋 Watchlist: Error loading")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_watchlist(update, context):
    """Xem watchlist hiện tại."""
    try:
        from watchlist import get_watchlist
        symbols = get_watchlist()

        if not symbols:
            await update.message.reply_text(
                "📋 Watchlist trống. Dùng /add `SYMBOL` để thêm.",
                parse_mode="Markdown",
            )
            return

        symbol_list = "\n".join(f"  • `{s}`" for s in symbols)
        await update.message.reply_text(
            f"📋 *Watchlist* ({len(symbols)} symbols):\n\n{symbol_list}\n\n"
            "Dùng /add `SYM` hoặc /remove `SYM` để quản lý.",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_add(update, context):
    """Thêm symbol vào watchlist."""
    if not context.args:
        await update.message.reply_text(
            "⚠️ Cần chỉ định symbol.\nVD: /add `BTCUSDT`",
            parse_mode="Markdown",
        )
        return

    symbol = context.args[0].strip().upper()

    try:
        from watchlist import add_symbol
        result = add_symbol(symbol)

        if result.get("added"):
            await update.message.reply_text(
                f"✅ Đã thêm `{symbol}` vào watchlist.\n"
                f"📋 Total: {len(result.get('watchlist', []))} symbols",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                f"⚠️ `{symbol}` đã có trong watchlist.",
                parse_mode="Markdown",
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_remove(update, context):
    """Xóa symbol khỏi watchlist."""
    if not context.args:
        await update.message.reply_text(
            "⚠️ Cần chỉ định symbol.\nVD: /remove `SOLUSDT`",
            parse_mode="Markdown",
        )
        return

    symbol = context.args[0].strip().upper()

    try:
        from watchlist import remove_symbol
        result = remove_symbol(symbol)

        if result.get("removed"):
            await update.message.reply_text(
                f"🗑️ Đã xóa `{symbol}` khỏi watchlist.\n"
                f"📋 Còn lại: {len(result.get('watchlist', []))} symbols",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                f"⚠️ `{symbol}` không có trong watchlist.",
                parse_mode="Markdown",
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_scan(update, context):
    """Scan watchlist — Trend Template + VCP."""
    await update.message.reply_text("🔄 Đang scan watchlist... Vui lòng chờ.")

    try:
        from watchlist import get_watchlist
        from analysis import scan_symbols

        symbols = get_watchlist()
        if not symbols:
            await update.message.reply_text("📋 Watchlist trống. Dùng /add để thêm symbols.")
            return

        # Check MCP
        import config
        mcp = None
        if config.MCP_ENABLED:
            try:
                from mcp_client import get_mcp_client
                mcp = get_mcp_client()
            except Exception:
                pass

        results = await scan_symbols(symbols, mcp)

        if not results:
            await update.message.reply_text("⚠️ Không scan được symbol nào. Kiểm tra MCP connection.")
            return

        # Format results table
        lines = [f"📊 *Scan Results* ({len(results)} symbols)\n"]
        lines.append("```")
        lines.append(f"{'Symbol':<10} {'Price':>10} {'TT':>4} {'VCP':>5} {'Vol%':>6}")
        lines.append("─" * 40)

        for r in results:
            tt_score = r.get("trend_template", {}).get("score", "?")
            tt_max = 8
            vcp = "⭐" if r.get("vcp", {}).get("detected") else ""
            vol_ratio = r.get("vcp", {}).get("volume_ratio", 0)
            vol_pct = f"{vol_ratio*100:.0f}%" if vol_ratio else "N/A"
            price = r.get("price", 0)

            if price >= 1000:
                price_str = f"{price:,.0f}"
            elif price >= 1:
                price_str = f"{price:,.2f}"
            else:
                price_str = f"{price:.4f}"

            lines.append(
                f"{r.get('symbol', '?'):<10} {price_str:>10} {tt_score}/{tt_max}  {vcp:<3} {vol_pct:>5}"
            )

        lines.append("```")

        # VCP highlights
        vcp_setups = [r for r in results if r.get("vcp", {}).get("detected")]
        if vcp_setups:
            lines.append("\n🎯 *VCP Setups:*")
            for r in vcp_setups:
                vcp_info = r.get("vcp", {})
                pivot = vcp_info.get("pivot_level", 0)
                lines.append(
                    f"• `{r['symbol']}` — Vol: {vcp_info.get('volume_ratio', 0)*100:.0f}% avg, "
                    f"Pivot: {pivot:,.2f}"
                )

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    except Exception as e:
        log.error(f"Scan error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Scan failed: {e}")


async def cmd_brief(update, context):
    """Chạy Morning Brief on-demand."""
    await update.message.reply_text("🌅 Đang chạy Morning Brief... Vui lòng chờ 30-60s.")

    try:
        from brief import generate_morning_brief
        result = await generate_morning_brief()

        if result and result.get("success"):
            await update.message.reply_text(
                "✅ Morning Brief đã gửi! Kiểm tra chat để xem report đầy đủ."
            )
        else:
            error = result.get("error", "Unknown") if result else "No result"
            await update.message.reply_text(f"⚠️ Brief hoàn thành với lỗi: {error}")

    except Exception as e:
        log.error(f"Brief trigger error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Brief failed: {e}")


async def cmd_vision(update, context):
    """AI Vision — phân tích chart screenshot bằng Claude Vision."""
    if not context.args:
        await update.message.reply_text(
            "⚠️ Cần chỉ định symbol.\nVD: /vision `BTCUSDT`",
            parse_mode="Markdown",
        )
        return

    symbol = context.args[0].strip().upper()
    await update.message.reply_text(f"👁️ Đang phân tích chart `{symbol}`... Vui lòng chờ.", parse_mode="Markdown")

    try:
        import config
        from pathlib import Path

        # Check for existing screenshot
        screenshots_dir = Path(__file__).parent / "screenshots"
        screenshot_path = None

        # Try to capture new screenshot via MCP
        if config.MCP_ENABLED:
            try:
                from mcp_client import get_mcp_client
                mcp = get_mcp_client()
                health = await mcp.health_check()
                if health.get("connected"):
                    from datetime import datetime as dt
                    screenshot_path = await mcp.capture_screenshot(
                        symbol=symbol,
                        timeframe="D",
                        region="chart",
                        save_path=screenshots_dir / f"vision_{symbol}_{dt.now().strftime('%Y%m%d_%H%M%S')}.png"
                    )
            except Exception as e:
                log.warning(f"Vision screenshot capture failed: {e}")

        # Fallback: look for latest screenshot of this symbol
        if not screenshot_path or not Path(screenshot_path).exists():
            if screenshots_dir.exists():
                candidates = sorted(
                    screenshots_dir.glob(f"*{symbol}*.png"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if candidates:
                    screenshot_path = candidates[0]

        if not screenshot_path or not Path(screenshot_path).exists():
            await update.message.reply_text(
                f"⚠️ Không tìm thấy screenshot cho `{symbol}`.\n"
                "Cần TradingView MCP connected hoặc screenshot sẵn có.",
                parse_mode="Markdown",
            )
            return

        # Run Vision analysis
        from vision import analyze_chart_vision, format_vision_telegram

        result = await analyze_chart_vision(
            image_path=Path(screenshot_path),
            symbol=symbol,
        )

        if result.get("error"):
            await update.message.reply_text(f"❌ Vision error: {result['error']}")
            return

        vision_text = format_vision_telegram(result)
        await update.message.reply_text(vision_text, parse_mode="Markdown")

    except Exception as e:
        log.error(f"Vision command error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Vision failed: {e}")


async def cmd_grade(update, context):
    """AI Mentor — chấm điểm setup Long/Short trên màn hình hiện tại."""
    await update.message.reply_text("👨‍🏫 Đang chụp và phân tích lệnh của bạn... Vui lòng chờ.", parse_mode="Markdown")

    try:
        import config
        from pathlib import Path

        if not config.MCP_ENABLED:
            await update.message.reply_text("⚠️ Tính năng này yêu cầu bật MCP_ENABLED = True.")
            return

        screenshots_dir = Path(__file__).parent / "screenshots"
        screenshot_path = None

        try:
            from mcp_client import get_mcp_client
            mcp = get_mcp_client()
            health = await mcp.health_check()
            if health.get("connected"):
                from datetime import datetime as dt
                # Chụp màn hình hiện tại (active_only=True) để không phá Bar Replay
                screenshot_path = await mcp.capture_screenshot(
                    symbol="active",
                    timeframe="active",
                    region="chart",
                    save_path=screenshots_dir / f"grade_{dt.now().strftime('%Y%m%d_%H%M%S')}.png",
                    active_only=True
                )
            else:
                await update.message.reply_text("⚠️ TradingView chưa kết nối (MCP CDP).")
                return
        except Exception as e:
            log.warning(f"Grade screenshot capture failed: {e}")
            await update.message.reply_text(f"❌ Lỗi chụp TradingView: {e}")
            return

        if not screenshot_path or not Path(screenshot_path).exists():
            await update.message.reply_text("⚠️ Không lấy được ảnh từ TradingView.")
            return

        # Run Vision analysis on the captured screenshot
        from vision import analyze_chart_vision, format_vision_telegram

        # Use symbol from args or fallback to "CHART"
        symbol = context.args[0].upper() if context.args else "ACTIVE CHART"

        result = await analyze_chart_vision(
            image_path=Path(screenshot_path),
            symbol=symbol,
        )

        if result.get("error"):
            await update.message.reply_text(f"\u274c Vision error: {result['error']}")
            return

        formatted = format_vision_telegram(result)
        await update.message.reply_text(formatted, parse_mode="Markdown")


    except Exception as e:
        log.error(f"Grade command error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Grade failed: {e}")


async def cmd_balance(update, context):
    """Xem Binance account balance."""
    try:
        import binance_client as binance_module

        client = binance_module.get_client()
        asset = context.args[0].upper() if context.args else "USDT"
        balance = await client.get_account_balance(asset)

        mode = []
        if client.dry_run:
            mode.append("DRY-RUN")
        mode.append("TESTNET" if client.testnet else "MAINNET")
        mode_str = ", ".join(mode)

        await update.message.reply_text(
            f"💰 *Binance Balance*\n\n"
            f"- Asset: `{asset}`\n"
            f"- Balance: `${balance:,.2f}`\n"
            f"- Mode: `{mode_str}`",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


# ── Inline Keyboard Callback ──────────────────────────────────────────────

async def button_callback(update, context):
    """Handle inline keyboard button presses."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "status":
        # Re-use status logic
        await query.message.reply_text("🔄 Loading status...")
        # Simulate Update object for cmd_status
        await cmd_status_inline(query.message)
    elif data == "watchlist":
        await cmd_watchlist_inline(query.message)
    elif data == "scan":
        await query.message.reply_text("🔄 Đang scan watchlist... Vui lòng chờ.")
        await cmd_scan_inline(query.message)
    elif data == "brief":
        await query.message.reply_text("🌅 Đang chạy Morning Brief... Vui lòng chờ 30-60s.")
        await cmd_brief_inline(query.message)


async def cmd_status_inline(message):
    """Status handler for inline buttons (receives Message instead of Update)."""
    import config
    lines = [
        "🔧 *System Status*\n",
        f"⏰ Time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        f"🌐 Server: FastAPI v7.0 on :{config.PORT}",
    ]
    rag_status = "✅" if config.RAG_ENABLED and config.ANTHROPIC_API_KEY else "❌"
    mcp_status = "✅" if config.MCP_ENABLED else "❌"
    brief_status = "✅" if config.BRIEF_ENABLED else "❌"
    lines.append(f"🧠 RAG: {rag_status}  |  🖥️ MCP: {mcp_status}  |  ⏰ Brief: {brief_status}")

    try:
        from watchlist import get_watchlist
        wl = get_watchlist()
        lines.append(f"📋 Watchlist: {len(wl)} symbols")
    except Exception:
        pass

    await message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_watchlist_inline(message):
    """Watchlist handler for inline buttons."""
    try:
        from watchlist import get_watchlist
        symbols = get_watchlist()
        if symbols:
            symbol_list = ", ".join(f"`{s}`" for s in symbols)
            await message.reply_text(
                f"📋 *Watchlist* ({len(symbols)}): {symbol_list}",
                parse_mode="Markdown",
            )
        else:
            await message.reply_text("📋 Watchlist trống.")
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")


async def cmd_scan_inline(message):
    """Scan handler for inline buttons."""
    try:
        from watchlist import get_watchlist
        from analysis import scan_symbols
        import config

        symbols = get_watchlist()
        if not symbols:
            await message.reply_text("📋 Watchlist trống.")
            return

        mcp = None
        if config.MCP_ENABLED:
            try:
                from mcp_client import get_mcp_client
                mcp = get_mcp_client()
            except Exception:
                pass

        results = await scan_symbols(symbols, mcp)
        if results:
            summary = []
            for r in results:
                tt = r.get("trend_template", {}).get("score", "?")
                vcp = "⭐" if r.get("vcp", {}).get("detected") else ""
                summary.append(f"`{r['symbol']}` TT:{tt}/8 {vcp}")
            await message.reply_text(
                f"📊 *Scan* ({len(results)} symbols):\n" + "\n".join(summary),
                parse_mode="Markdown",
            )
        else:
            await message.reply_text("⚠️ Không scan được.")
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")


async def cmd_brief_inline(message):
    """Brief handler for inline buttons."""
    try:
        from brief import generate_morning_brief
        result = await generate_morning_brief()
        if result and result.get("success"):
            await message.reply_text("✅ Morning Brief đã gửi!")
        else:
            await message.reply_text("⚠️ Brief gặp lỗi.")
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")


# ── Bot Lifecycle ─────────────────────────────────────────────────────────

def start_bot():
    """Start Telegram bot in a background thread (polling mode)."""
    global _bot_app, _bot_thread

    import config
    if not config.TELEGRAM_BOT_TOKEN:
        log.warning("TELEGRAM_BOT_TOKEN not set — Telegram Bot disabled")
        return

    try:
        _get_imports()
    except ImportError:
        log.warning("python-telegram-bot not installed — run: pip install python-telegram-bot")
        return

    from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler

    def _run_bot():
        """Bot runner in separate thread with its own event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Build bot — force IPv4 to fix async httpx ConnectError on Windows
        # httpx AsyncClient tries IPv6 first, which may not be routed on some networks.
        # Fix: inject local_address="0.0.0.0" transport into HTTPXRequest._client_kwargs
        from telegram.request import HTTPXRequest
        import httpx as _httpx

        _proxy = config.TELEGRAM_PROXY_URL or None
        request = HTTPXRequest(proxy=_proxy)
        # Inject IPv4-only transport (overrides default which allows IPv6)
        request._client_kwargs["transport"] = _httpx.AsyncHTTPTransport(
            local_address="0.0.0.0",
        )
        # Rebuild internal client with patched kwargs
        request._client = request._build_client()

        app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).request(request).build()
        log.info("🤖 Telegram Bot using IPv4-forced async transport (fix for Windows)")


        # Register command handlers
        app.add_handler(CommandHandler("start", cmd_start))
        app.add_handler(CommandHandler("help", cmd_help))
        app.add_handler(CommandHandler("status", cmd_status))
        app.add_handler(CommandHandler("watchlist", cmd_watchlist))
        app.add_handler(CommandHandler("add", cmd_add))
        app.add_handler(CommandHandler("remove", cmd_remove))
        app.add_handler(CommandHandler("scan", cmd_scan))
        app.add_handler(CommandHandler("brief", cmd_brief))
        app.add_handler(CommandHandler("vision", cmd_vision))
        app.add_handler(CommandHandler("grade", cmd_grade))
        app.add_handler(CommandHandler("balance", cmd_balance))
        app.add_handler(CallbackQueryHandler(button_callback))

        log.info("🤖 Telegram Bot started (polling mode)")
        app.run_polling(drop_pending_updates=True)

    _bot_thread = threading.Thread(target=_run_bot, daemon=True, name="telegram-bot")
    _bot_thread.start()
    log.info("🤖 Telegram Bot thread launched")


def stop_bot():
    """Stop Telegram bot gracefully."""
    global _bot_app
    if _bot_app:
        log.info("🤖 Telegram Bot stopping...")
        # Bot thread is daemon — will terminate with main process
    _bot_app = None
