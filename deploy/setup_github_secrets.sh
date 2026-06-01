#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════════
# setup_github_secrets.sh — Đăng ký GitHub Secrets cho CI/CD Pipeline
# V2 Hardened — TradingBot 3-Server Pipeline
#
# ❗ Chạy trên máy LOCAL (Windows/Linux/Mac) — KHÔNG chạy trên VPS
#
# Prerequisites:
#   1. GitHub CLI: https://cli.github.com/
#      winget install GitHub.cli       (Windows)
#      brew install gh                 (Mac)
#      apt install gh                  (Linux)
#   2. Đăng nhập: gh auth login
#   3. Tailscale Ephemeral Auth Key từ: https://login.tailscale.com/admin/settings/keys
#
# Usage:
#   bash deploy/setup_github_secrets.sh
#   # HOẶC chỉ dry-run (xem secrets sẽ được set):
#   DRY_RUN=true bash deploy/setup_github_secrets.sh
#
# ════════════════════════════════════════════════════════════════════════════

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

log()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()   { echo -e "${YELLOW}[!]${NC} $*"; }
err()    { echo -e "${RED}[✗]${NC} $*" >&2; }
info()   { echo -e "${BLUE}[→]${NC} $*"; }
section(){ echo -e "\n${CYAN}══ $* ══${NC}"; }

DRY_RUN="${DRY_RUN:-false}"

# ── Detect repo from git remote ──────────────────────────────────────────────
REPO=$(git remote get-url origin 2>/dev/null | \
       sed 's|git@github.com:||; s|https://github.com/||; s|\.git$||' || echo "")

if [[ -z "$REPO" ]]; then
    err "Cannot detect GitHub repo from git remote. Set REPO env var:"
    err "  export REPO=YOUR_ORG/TradingViewProject"
    exit 1
fi

echo -e "${CYAN}"
echo "═══════════════════════════════════════════════════════════"
echo "  🔐 GitHub Secrets Setup — CI/CD Pipeline V2 Hardened    "
echo "  Repo: ${REPO}                                           "
echo "  Mode: ${DRY_RUN}                                        "
echo "═══════════════════════════════════════════════════════════"
echo -e "${NC}"

# ── Check gh CLI ─────────────────────────────────────────────────────────────
if ! command -v gh &>/dev/null; then
    err "GitHub CLI (gh) not installed."
    err "Install: https://cli.github.com/"
    exit 1
fi

if ! gh auth status &>/dev/null; then
    err "Not logged in to GitHub CLI. Run: gh auth login"
    exit 1
fi

log "GitHub CLI: $(gh --version | head -1)"
log "Repo: https://github.com/${REPO}"

# ── Helper function ───────────────────────────────────────────────────────────
set_secret() {
    local name="$1"
    local value="$2"
    local description="${3:-}"

    if [[ -z "$value" || "$value" == "YOUR_"* || "$value" == "PLACEHOLDER" ]]; then
        warn "SKIP ${name} — value not set (${description})"
        return
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "  ${BLUE}[DRY-RUN]${NC} Would set: ${name} = ${value:0:4}****"
        return
    fi

    echo -n "  Setting ${name}..."
    echo "$value" | gh secret set "$name" --repo "$REPO" --body -
    echo -e " ${GREEN}✓${NC}"
}

# ════════════════════════════════════════════════════════════════════════════
# INTERACTIVE INPUT — Thu thập secrets từ user
# ════════════════════════════════════════════════════════════════════════════

section "Nhập thông tin servers (Enter để skip)"

read_input() {
    local prompt="$1"
    local default="${2:-}"
    local result
    read -rp "  ${prompt} [${default}]: " result
    echo "${result:-$default}"
}

echo -e "${YELLOW}⚠️  Các giá trị bạn nhập sẽ được đẩy thẳng vào GitHub Secrets (encrypted).${NC}"
echo -e "${YELLOW}   KHÔNG lưu vào file, KHÔNG hiện trong log.${NC}"
echo ""

# ── Server IPs (Tailscale) ───────────────────────────────────────────────────
section "Server IPs (Tailscale 100.x.x.x)"
SERVER_A_IP=$(read_input "SERVER_A_IP (Tailscale IP of Server A Gateway)" "100.x.x.1")
SERVER_B_IP=$(read_input "SERVER_B_IP (Tailscale IP of Server B Execution)" "100.x.x.2")
SERVER_C_IP=$(read_input "SERVER_C_IP (Tailscale IP of Server C AI Core)" "100.x.x.3")

# ── SSH Key ──────────────────────────────────────────────────────────────────
section "SSH Private Key"
echo "  Path to ED25519 private key (dùng để CI/CD SSH vào servers):"
read -rp "  Key path [~/.ssh/id_ed25519]: " SSH_KEY_PATH
SSH_KEY_PATH="${SSH_KEY_PATH:-$HOME/.ssh/id_ed25519}"

SSH_PRIVATE_KEY=""
if [[ -f "$SSH_KEY_PATH" ]]; then
    SSH_PRIVATE_KEY=$(cat "$SSH_KEY_PATH")
    log "SSH key loaded: $SSH_KEY_PATH"
else
    warn "Key not found: $SSH_KEY_PATH"
    warn "Tạo key mới:"
    warn "  ssh-keygen -t ed25519 -C 'tradingbot-ci-cd'"
    warn "  ssh-copy-id -i ~/.ssh/id_ed25519.pub botuser@SERVER_A_IP"
    warn "  ssh-copy-id -i ~/.ssh/id_ed25519.pub botuser@SERVER_C_IP"
fi

# ── Tailscale ────────────────────────────────────────────────────────────────
section "Tailscale Ephemeral Auth Key"
echo "  Lấy tại: https://login.tailscale.com/admin/settings/keys"
echo "  Tick: Ephemeral, Reusable, Tags: tag:ci"
read -rsp "  TAILSCALE_AUTHKEY: " TAILSCALE_AUTHKEY
echo ""

# ── Telegram ─────────────────────────────────────────────────────────────────
section "Telegram (Alert notifications)"
read -rp "  TELEGRAM_BOT_TOKEN: " TELEGRAM_BOT_TOKEN
read -rp "  TELEGRAM_CHAT_ID: " TELEGRAM_CHAT_ID

# ── Trading Bot Secrets ───────────────────────────────────────────────────────
section "TradingBot Application Secrets"
read -rsp "  WEBHOOK_SECRET (TradingView → Server A): " WEBHOOK_SECRET; echo ""
read -rsp "  VPS_BUFFER_SECRET (Server A → Server C consume): " VPS_BUFFER_SECRET; echo ""
read -rsp "  SERVER_B_SECRET (Server C → Server B execute): " SERVER_B_SECRET; echo ""

# ── AI API Keys ───────────────────────────────────────────────────────────────
section "AI Provider API Keys"
read -rsp "  ANTHROPIC_API_KEY (sk-ant-...): " ANTHROPIC_API_KEY; echo ""
read -rsp "  GEMINI_API_KEY: " GEMINI_API_KEY; echo ""

# ── UptimeRobot ──────────────────────────────────────────────────────────────
section "UptimeRobot (#14 Monitoring)"
echo "  Lấy tại: https://uptimerobot.com/dashboard#api → Main API Key"
read -rp "  UPTIMEROBOT_API_KEY (optional): " UPTIMEROBOT_API_KEY

# ── Dashboard Token ───────────────────────────────────────────────────────────
section "Dashboard Auth Token"
AUTO_DASH_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(16))" 2>/dev/null || openssl rand -hex 16)
read -rp "  DASHBOARD_TOKEN [auto-generate ${AUTO_DASH_TOKEN:0:8}****]: " DASHBOARD_TOKEN
DASHBOARD_TOKEN="${DASHBOARD_TOKEN:-$AUTO_DASH_TOKEN}"

# ════════════════════════════════════════════════════════════════════════════
# APPLY SECRETS
# ════════════════════════════════════════════════════════════════════════════

section "Registering GitHub Secrets → ${REPO}"
[[ "$DRY_RUN" == "true" ]] && warn "DRY-RUN mode — no secrets will be set"

# Infrastructure
set_secret "SERVER_A_IP"          "$SERVER_A_IP"          "Tailscale IP Server A"
set_secret "SERVER_B_IP"          "$SERVER_B_IP"          "Tailscale IP Server B"
set_secret "SERVER_C_IP"          "$SERVER_C_IP"          "Tailscale IP Server C"
set_secret "SSH_PRIVATE_KEY"      "$SSH_PRIVATE_KEY"      "ED25519 private key for CI/CD SSH"
set_secret "TAILSCALE_AUTHKEY"    "$TAILSCALE_AUTHKEY"    "Tailscale ephemeral auth key"

# Notifications
set_secret "TELEGRAM_BOT_TOKEN"   "$TELEGRAM_BOT_TOKEN"   "Telegram bot token"
set_secret "TELEGRAM_CHAT_ID"     "$TELEGRAM_CHAT_ID"     "Telegram chat ID"

# Application
set_secret "WEBHOOK_SECRET"       "$WEBHOOK_SECRET"       "TradingView webhook secret"
set_secret "VPS_BUFFER_SECRET"    "$VPS_BUFFER_SECRET"    "VBS consume buffer secret"
set_secret "SERVER_B_SECRET"      "$SERVER_B_SECRET"      "Server B execution secret"
set_secret "DASHBOARD_TOKEN"      "$DASHBOARD_TOKEN"      "Dashboard bearer token"

# AI
set_secret "ANTHROPIC_API_KEY"    "$ANTHROPIC_API_KEY"    "Anthropic Claude API key"
set_secret "GEMINI_API_KEY"       "$GEMINI_API_KEY"       "Google Gemini API key"

# Monitoring
set_secret "UPTIMEROBOT_API_KEY"  "$UPTIMEROBOT_API_KEY"  "UptimeRobot monitoring API key"

# ════════════════════════════════════════════════════════════════════════════
# VERIFY
# ════════════════════════════════════════════════════════════════════════════

section "Verification"

if [[ "$DRY_RUN" != "true" ]]; then
    echo ""
    info "Listing registered secrets:"
    gh secret list --repo "$REPO" 2>/dev/null | while read -r line; do
        SECRET_NAME=$(echo "$line" | awk '{print $1}')
        echo -e "  ${GREEN}✓${NC} $SECRET_NAME"
    done

    echo ""
    log "All secrets registered ✅"
fi

# ════════════════════════════════════════════════════════════════════════════
# NEXT STEPS
# ════════════════════════════════════════════════════════════════════════════

echo ""
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ GitHub Secrets Setup Complete                         ${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  📋 Verify tại: https://github.com/${REPO}/settings/secrets/actions"
echo ""
echo "  ⚠️  Còn cần làm thủ công:"
echo ""
echo "  [1] Copy SSH public key vào servers:"
echo "      ssh-copy-id -i ${SSH_KEY_PATH}.pub botuser@\${SERVER_A_IP}"
echo "      ssh-copy-id -i ${SSH_KEY_PATH}.pub botuser@\${SERVER_C_IP}"
echo ""
echo "  [2] Tailscale — Add tag 'ci' vào policy ACL:"
echo "      https://login.tailscale.com/admin/acls"
echo "      Thêm: {\"action\": \"accept\", \"src\": [\"tag:ci\"], \"dst\": [\"*:22\"]}"
echo ""
echo "  [3] Test CI/CD pipeline:"
echo "      git commit --allow-empty -m 'test: trigger CI/CD'"
echo "      git push origin main"
echo "      # Xem tại: https://github.com/${REPO}/actions"
echo ""
echo "  [4] (Optional) Migrate Tailscale → OAuth (khi scopes được fix):"
echo "      https://login.tailscale.com/admin/settings/oauth"
echo "      Set TS_OAUTH_CLIENT_ID + TS_OAUTH_SECRET"
echo ""
