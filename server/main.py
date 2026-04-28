import json
import logging
from datetime import datetime, timezone

from flask import Flask, request, jsonify

import config

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ─── HEALTH CHECK ─────────────────────────────────────────────────────────────

@app.get("/tv_health_check")
def tv_health_check():
    return jsonify({
        "status": "ok",
        "service": "TradingView Webhook Server",
        "time": datetime.now(timezone.utc).isoformat(),
    })


# ─── WEBHOOK ──────────────────────────────────────────────────────────────────

@app.post("/webhook")
def webhook():
    # Parse payload first — TradingView cannot send custom HTTP headers,
    # so the secret may live in the JSON body or the query string instead.
    try:
        payload = request.get_json(force=True, silent=True) or {}
    except Exception:
        return jsonify({"error": "invalid JSON"}), 400

    secret = (
        request.headers.get("X-TV-Secret")
        or request.args.get("secret")
        or payload.pop("secret", None)
        or ""
    )
    if secret != config.WEBHOOK_SECRET:
        log.warning("Unauthorized webhook attempt from %s", request.remote_addr)
        return jsonify({"error": "unauthorized"}), 401

    if not payload:
        return jsonify({"error": "empty payload"}), 400

    action = payload.get("action", "").lower()
    symbol = payload.get("symbol", "")
    price  = payload.get("price", "")
    ts     = payload.get("time", "")

    log.info("ALERT  action=%s  symbol=%s  price=%s  time=%s", action, symbol, price, ts)

    # Place order if Binance credentials are configured
    if config.BINANCE_API_KEY and action in ("buy", "sell"):
        result = _place_binance_order(action, symbol, price)
        return jsonify({"received": True, "order": result})

    return jsonify({"received": True, "order": None})


# ─── BINANCE ORDER (optional) ─────────────────────────────────────────────────

def _place_binance_order(action: str, symbol: str, price: str) -> dict:
    """Minimal Binance market-order placement via REST API."""
    import hmac, hashlib, time
    import requests as req

    base = "https://testnet.binance.vision" if config.BINANCE_TESTNET else "https://api.binance.com"
    side = "BUY" if action == "buy" else "SELL"
    params = {
        "symbol":    symbol.replace("/", "").upper(),
        "side":      side,
        "type":      "MARKET",
        "quoteOrderQty": 10,   # spend 10 USDT per trade — adjust as needed
        "timestamp": int(time.time() * 1000),
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    sig = hmac.new(config.BINANCE_API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    params["signature"] = sig

    headers = {"X-MBX-APIKEY": config.BINANCE_API_KEY}
    resp = req.post(f"{base}/api/v3/order", params=params, headers=headers, timeout=10)
    log.info("Binance response: %s", resp.text)
    return resp.json()


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("Starting TradingView Webhook Server on %s:%s", config.HOST, config.PORT)
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
