/**
 * Cloudflare Worker — TradingView Webhook Proxy
 * ════════════════════════════════════════════════════════════════
 * Nhận webhook từ TradingView → forward qua Telegram Bot API.
 * PC nhà chỉ cần polling (outbound) — không cần tunnel/mở port.
 *
 * Environment Variables (set via `wrangler secret put`):
 *   WEBHOOK_SECRET   - Shared secret with TradingView alert
 *   TELEGRAM_TOKEN   - Telegram Bot token (from @BotFather)
 *   TELEGRAM_CHAT_ID - Chat/group ID to send signals to
 *
 * Deploy:
 *   npx wrangler deploy
 *
 * Test:
 *   curl -X POST https://trading-webhook-proxy.YOUR.workers.dev \
 *     -H "Content-Type: application/json" \
 *     -d '{"secret":"xxx","action":"buy","symbol":"BTCUSDT","price":"67500"}'
 * ════════════════════════════════════════════════════════════════
 */

export default {
  async fetch(request, env) {
    // ── CORS preflight ────────────────────────────────────────
    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "POST",
          "Access-Control-Allow-Headers": "Content-Type",
        },
      });
    }

    // ── Only accept POST ──────────────────────────────────────
    if (request.method !== "POST") {
      return jsonResponse({ error: "Method Not Allowed" }, 405);
    }

    // ── Parse payload ─────────────────────────────────────────
    let payload;
    try {
      payload = await request.json();
    } catch (e) {
      return jsonResponse({ error: "Invalid JSON body" }, 400);
    }

    // ── Verify webhook secret ─────────────────────────────────
    const secret = payload.secret || "";
    if (!secret || secret !== env.WEBHOOK_SECRET) {
      return jsonResponse({ error: "Unauthorized" }, 401);
    }

    // ── Validate required fields ──────────────────────────────
    if (!payload.action || !payload.symbol) {
      return jsonResponse({ error: "Missing required fields: action, symbol" }, 400);
    }

    // ── Build signal payload for Telegram ─────────────────────
    const signalData = JSON.stringify({
      action: payload.action,
      symbol: payload.symbol,
      price: payload.price || "0",
      quoteQty: payload.quoteQty || payload.size || 10,
      time: payload.time || new Date().toISOString(),
      secret: payload.secret,
      _source: "cloudflare_worker",
      _worker_ts: Date.now(),
    });

    // ── Forward to Telegram as /signal command ────────────────
    const telegramUrl = `https://api.telegram.org/bot${env.TELEGRAM_TOKEN}/sendMessage`;

    try {
      const tgResponse = await fetch(telegramUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: env.TELEGRAM_CHAT_ID,
          text: `/signal ${signalData}`,
        }),
      });

      const tgResult = await tgResponse.json();

      if (!tgResult.ok) {
        console.error("Telegram API error:", tgResult);
        return jsonResponse(
          {
            ok: false,
            error: "Telegram delivery failed",
            detail: tgResult.description || "Unknown error",
          },
          502
        );
      }

      return jsonResponse({
        ok: true,
        signal_forwarded: true,
        symbol: payload.symbol,
        action: payload.action,
        timestamp: new Date().toISOString(),
      });
    } catch (e) {
      console.error("Fetch error:", e);
      return jsonResponse({ ok: false, error: e.message }, 500);
    }
  },
};

// ── Helper ────────────────────────────────────────────────────
function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
    },
  });
}
