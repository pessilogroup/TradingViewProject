#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════════
# setup_monitoring.sh — V2 Hardened: logrotate + UptimeRobot bootstrap
# Chạy trên SERVER A (Gateway) sau khi docker-compose đã up
#
# Usage:
#   chmod +x setup_monitoring.sh
#   sudo ./setup_monitoring.sh
#
# Env vars cần có trước khi chạy:
#   UPTIMEROBOT_API_KEY   — API key từ https://uptimerobot.com/dashboard#api
#   SERVER_A_PUBLIC_IP    — IP hoặc domain của Server A (hoặc Cloudflare URL)
#   TELEGRAM_BOT_TOKEN    — Bot token (giống .env)
#   TELEGRAM_CHAT_ID      — Chat ID (giống .env)
# ════════════════════════════════════════════════════════════════════════════

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log_ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_err()  { echo -e "${RED}[ERR]${NC} $*"; }

# ── 1. Cài logrotate nếu chưa có ───────────────────────────────────────────
echo ""
echo "═══ #12 Linux logrotate Setup ════════════════════════════════════════"

if ! command -v logrotate &>/dev/null; then
    log_warn "logrotate not found — installing..."
    apt-get update -q && apt-get install -y logrotate
fi

LOGROTATE_SRC="${SCRIPT_DIR}/tradingbot-logrotate"
LOGROTATE_DEST="/etc/logrotate.d/tradingbot"

if [[ ! -f "$LOGROTATE_SRC" ]]; then
    log_err "Missing: ${LOGROTATE_SRC} — aborting logrotate setup"
else
    cp "$LOGROTATE_SRC" "$LOGROTATE_DEST"
    chmod 644 "$LOGROTATE_DEST"
    chown root:root "$LOGROTATE_DEST"

    # Dry-run verify
    if logrotate -d "$LOGROTATE_DEST" 2>&1 | grep -q "error"; then
        log_err "logrotate config has errors — check $LOGROTATE_DEST"
    else
        log_ok "logrotate config installed: $LOGROTATE_DEST"
        log_ok "  → Docker container logs: daily, keep 3, compress"
        log_ok "  → App logs (/app/logs/*.log): daily, keep 7, compress"
    fi

    # Ensure logrotate runs daily via cron (thường đã có sẵn)
    if [[ -f /etc/cron.daily/logrotate ]]; then
        log_ok "cron.daily/logrotate already active"
    else
        log_warn "No cron.daily/logrotate found — logrotate won't auto-run"
        log_warn "  → Add manually: echo '0 2 * * * root /usr/sbin/logrotate /etc/logrotate.conf' >> /etc/crontab"
    fi
fi

# ── 2. UptimeRobot API Setup (#14) ─────────────────────────────────────────
echo ""
echo "═══ #14 UptimeRobot Monitor Setup ════════════════════════════════════"

UPTIMEROBOT_API_KEY="${UPTIMEROBOT_API_KEY:-}"
SERVER_A_PUBLIC_IP="${SERVER_A_PUBLIC_IP:-}"
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"

if [[ -z "$UPTIMEROBOT_API_KEY" ]]; then
    log_warn "UPTIMEROBOT_API_KEY not set — skipping UptimeRobot API setup"
    log_warn "Manual steps at: https://uptimerobot.com/dashboard#newMonitorBtn"
    log_warn "  1. Type: HTTP(s) | Friendly Name: TradingBot Server A"
    log_warn "  2. URL: http://${SERVER_A_PUBLIC_IP:-YOUR_IP}:5000/health"
    log_warn "  3. Monitoring Interval: 5 minutes"
    log_warn "  4. Alert When: Not containing 'healthy'"
    log_warn "  5. Telegram: https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage"
    echo ""
else
    HEALTH_URL="http://${SERVER_A_PUBLIC_IP}:5000/health"
    log_ok "Creating UptimeRobot HTTP monitor for ${HEALTH_URL}..."

    # Create HTTP monitor via UptimeRobot API v2
    RESPONSE=$(curl -s -X POST "https://api.uptimerobot.com/v2/newMonitor" \
        -H "Content-Type: application/json" \
        -d "{
            \"api_key\": \"${UPTIMEROBOT_API_KEY}\",
            \"format\": \"json\",
            \"type\": 2,
            \"url\": \"${HEALTH_URL}\",
            \"friendly_name\": \"TradingBot — Server A /health\",
            \"interval\": 300,
            \"keyword_type\": 2,
            \"keyword_value\": \"healthy\"
        }")

    STATUS=$(echo "$RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('stat','fail'))" 2>/dev/null || echo "fail")

    if [[ "$STATUS" == "ok" ]]; then
        MONITOR_ID=$(echo "$RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('monitor',{}).get('id','?'))" 2>/dev/null || echo "?")
        log_ok "UptimeRobot monitor created! ID: ${MONITOR_ID}"
        log_ok "  URL: ${HEALTH_URL}"
        log_ok "  Checks every 5 minutes"
        log_ok "  Alerts when response does not contain 'healthy'"
    else
        log_err "UptimeRobot API error: ${RESPONSE}"
        log_warn "Create manually at: https://uptimerobot.com/dashboard#newMonitorBtn"
    fi

    # ── Cloudflare HTTP check (optional — nếu có Cloudflare API token) ─────
    CF_API_TOKEN="${CF_API_TOKEN:-}"
    CF_ZONE_ID="${CF_ZONE_ID:-}"
    if [[ -n "$CF_API_TOKEN" && -n "$CF_ZONE_ID" ]]; then
        log_ok "Cloudflare healthcheck not available via API — configure in dashboard:"
        log_warn "  Cloudflare Dashboard → Notifications → Health Checks"
        log_warn "  URL: ${HEALTH_URL}, Path: /health, Interval: 60s"
    fi
fi

# ── 3. Tóm tắt ─────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "  V2 Monitoring Setup Complete"
echo "════════════════════════════════════════════════════════════════════"
echo "  #12 logrotate  → /etc/logrotate.d/tradingbot"
echo "  #14 UptimeRobot→ Dashboard: https://uptimerobot.com/dashboard"
echo ""
echo "  Verify logrotate: logrotate -v /etc/logrotate.d/tradingbot"
echo "  Force rotate now: logrotate -f /etc/logrotate.d/tradingbot"
echo "════════════════════════════════════════════════════════════════════"
