# Investigation Report: FastAPI Router and Telegram Bot Command Setup

This report contains findings on how FastAPI routes and Telegram bot commands are structured in the codebase, and proposes a design for a new `/scan_all` Telegram command that runs in the background.

---

## 1. Observation

Direct code observations from the workspace:

### FastAPI Router Setup
* **Main Application Setup**: In `nerves/workers/trading/main.py`:
  * Line 265: `app = FastAPI(title="TradingView Webhook Server", version="7.6", lifespan=lifespan)`
  * Line 272: `app.include_router(_webhook_router)` (where `_webhook_router` is imported at line 44: `from gateway.webhook import router as _webhook_router`)
  * Line 275-276:
    ```python
    from auth.routes import auth_router as _auth_router
    app.include_router(_auth_router)
    ```
  * Middleware is registered at lines 280 (AuthMiddleware) and 300 (ip_whitelist_middleware).
  * Direct route definitions exist for GET `/health`, `/dashboard`, `/daemon_dashboard`, `/`, `/tv_health_check`, `/api/mcp/status`, `/api/watchlist` (GET/POST/DELETE/PUT), `/api/scan/watchlist`, `/api/brief/trigger`, `/api/brief/latest`, `/api/indicator-signals`, `/api/indicator-signals/stats`, `/api/rag/query`, `/api/rag/status`, `/trades` (GET/stats/equity/analysis).

* **Webhook Ingress Route**: In `nerves/workers/trading/gateway/webhook.py`:
  * Line 45: `@router.post("/webhook")` parses incoming JSON payload, performs security checks (webhook secret + optional dashboard token bypass), verifies rate limits, and persists the signal.

* **Auth Router Structure**: In `nerves/workers/trading/auth/routes.py`:
  * Line 19: `auth_router = APIRouter(prefix="/auth", tags=["auth"])`
  * Line 27: `@auth_router.get("/login")` serves the login page or instructions.
  * Line 58: `@auth_router.get("/callback")` exchanges a one-time code for a session token, sets a signed `tg_session` cookie, and redirects to dashboard.
  * Line 143: `@auth_router.post("/telegram-callback")` handles Telegram Widget callback login verification.
  * Line 225: `@auth_router.get("/logout")` invalidates the session.

### Telegram Bot Setup
* **Bot Thread and Initialization**: In `nerves/workers/trading/telegram_bot.py`:
  * Line 2019-2021:
    ```python
    _bot_thread = threading.Thread(target=_run_bot, daemon=True, name="telegram-bot")
    _bot_thread.start()
    ```
  * Line 2017: `app.run_polling(drop_pending_updates=True, close_loop=False)` runs the python-telegram-bot application inside a daemon thread.
  * Line 1931: `_sender = TelegramSender(app)` instantiates a global `TelegramSender` singleton for outbound messages.
  * Line 1952-1987: `post_init(application)` registers bot commands in the Telegram menu via:
    ```python
    await application.bot.set_my_commands(commands)
    ```
  * Line 1990-2008: Command handlers are added:
    ```python
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("help",      cmd_help))
    ...
    app.add_handler(CommandHandler("positions", cmd_positions))
    ```
  * Claude SDK CLI telegram commands are registered separately if enabled (line 245 in `main.py` calls `_claude_tg.register_commands(_app, _claude_service)` which registers `/claude`, `/analyze`, `/claude_reset`, and `/claude_status` mapping to `claude_cli/telegram_commands.py`).

* **Interactive Scan Logic**:
  * Line 759: `async def cmd_scan_enhanced(update, context)` is registered as the handler for `/scan`.
  * Line 768: Symbols are retrieved from watchlist: `symbols = get_watchlist()`.
  * Line 781: Symbols are analyzed: `results = await scan_symbols(symbols, mcp)`.
  * Lines 787-825: Formats results and replies to the message.

---

## 2. Logic Chain

1. **Timeout Prevention**: 
   * Calling `analysis.scan_symbols` queries market data sequentially for each symbol via the local MCP client (which spawns subprocess Node.js instances).
   * For large watchlists, this sequential execution will take tens of seconds to minutes.
   * If a command handler runs synchronously in the Telegram polling flow, it block-waits for `scan_symbols`. This runs the risk of timing out python-telegram-bot's polling connection or resulting in an unresponsive bot.
   * *Conclusion*: We must launch the scanning logic asynchronously as a background task. In Python's asyncio, this is achieved by calling `asyncio.create_task(run_scan_all_background(chat_id))` inside the command handler `cmd_scan_all`. The command handler immediately replies to notify the user, freeing up the handler thread.

2. **Setup Filtering**:
   * To identify top setups from the scanned results, we must evaluate each symbol's Trend Template score and VCP status.
   * In `nerves/workers/trading/analysis.py`, the Trend Template score goes from `0` to `8` (`trend_template.score`), and VCP status is a boolean (`vcp.detected`).
   * *Conclusion*: We filter the results with the condition `score >= 6 or vcp_detected`.

3. **Broadcasting results**:
   * Once the background scan finishes, the bot should send the formatted message to the user who triggered the command.
   * In addition, it must broadcast the setups to the channel subscribers. In `telegram_bot.py`, `config.TELEGRAM_CHAT_IDS` contains the list of configured target chat IDs.
   * *Conclusion*: The background task will call `app.bot.send_message(chat_id, text, parse_mode="HTML")` for the initiating chat, and then loop through `config.TELEGRAM_CHAT_IDS` (skipping the initiating chat to avoid double-sending) to broadcast to other channels.

---

## 3. Caveats

* **MCP Dependency**: The VCP and Trend Template scanner requires the local TradingView Desktop MCP Client to be connected (via CDP port 9222). If TradingView Desktop is closed or the CDP port is not accessible, the background scan will fail or return errors.
* **Scan Duration**: The scan executes symbols sequentially using `batch_run`. If the watchlist grows very large (e.g. 50+ symbols), it may take several minutes to complete. An optimization would be parallel execution, but currently, TradingView MCP client serializes commands.
* **Rate Limits**: Spamming `/scan_all` could overload the MCP CDP interface. A cooldown mechanism should be implemented in production if users abuse the command.

---

## 4. Conclusion

A new Telegram bot command `/scan_all` should be added to `telegram_bot.py`. The design consists of:
1. **CommandHandler Registration**: Registering `/scan_all` pointing to `cmd_scan_all` and adding the command metadata to the `post_init` list.
2. **Non-Blocking Trigger**: `cmd_scan_all` immediately sends a "scanning..." placeholder message and executes `asyncio.create_task(run_scan_all_background(chat_id))`.
3. **Background Scanner**: `run_scan_all_background` runs the analysis, filters setups with `trend_template.score >= 6` or `vcp.detected`, formats the findings in a clean HTML preformatted table, and broadcasts to allowed chats in `config.TELEGRAM_CHAT_IDS`.

The detailed changes are proposed in `.agents/explorer_m1_3/proposed_scan_all.patch`.

---

## 5. Verification Method

To verify the implementation once applied:
1. **Verify Syntax and Registration**:
   * Run the python syntax check:
     ```powershell
     python -m py_compile nerves/workers/trading/telegram_bot.py
     ```
2. **Execute Tests**:
   * Run the project test suite using pytest to ensure no regressions in the telegram bot module:
     ```powershell
     pytest nerves/workers/trading/tests/unit/test_telegram_bot_p8.py
     ```
3. **Manual Verification**:
   * Ensure TradingView Desktop is running and connected via CDP.
   * Launch the FastAPI server: `python nerves/workers/trading/main.py`.
   * Open the Telegram bot and trigger `/scan_all`.
   * Verify that:
     * Bot immediately responds with: "🔄 Bắt đầu quét toàn bộ watchlist trong background..."
     * Bot remains responsive to other commands (like `/status`) during the scan.
     * Within 1-2 minutes, the bot sends the final scan result containing only setups with TT >= 6 or VCP detected.
