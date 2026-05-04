#!/bin/bash
# ════════════════════════════════════════════════════════════════
# Minervini AI Trading Bot — VPS Deploy Script
# Sprint 7.3: One-click deployment
# ════════════════════════════════════════════════════════════════
# Usage (on VPS):
#   curl -sSL https://raw.githubusercontent.com/.../deploy.sh | bash
#   OR: ./deploy/deploy.sh
# ════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Colors ────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }
info() { echo -e "${BLUE}[→]${NC} $1"; }

DEPLOY_DIR="/opt/trading-bot"
REPO_URL="https://github.com/pessilogroup/TradingViewProject.git"
BRANCH="main"

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Minervini AI Trading Bot — Deploy Script v7.3        ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo ""

# ── 1. Prerequisites ─────────────────────────────────────────
info "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    err "Docker not installed. Run: curl -fsSL https://get.docker.com | sh"
fi

if ! docker compose version &> /dev/null; then
    err "Docker Compose plugin not found. Install: apt install docker-compose-plugin"
fi

log "Docker $(docker --version | awk '{print $3}') detected"
log "Docker Compose $(docker compose version --short) detected"

# ── 2. Clone / Update Repo ────────────────────────────────────
if [ -d "$DEPLOY_DIR/.git" ]; then
    info "Updating existing installation..."
    cd "$DEPLOY_DIR"
    git fetch origin
    git checkout "$BRANCH"
    git pull origin "$BRANCH"
    log "Repository updated to latest $BRANCH"
else
    info "Fresh installation → $DEPLOY_DIR"
    sudo mkdir -p "$DEPLOY_DIR"
    sudo chown "$(whoami):$(whoami)" "$DEPLOY_DIR"
    git clone --branch "$BRANCH" "$REPO_URL" "$DEPLOY_DIR"
    cd "$DEPLOY_DIR"
    log "Repository cloned"
fi

# ── 3. Environment File ──────────────────────────────────────
if [ ! -f "$DEPLOY_DIR/.env" ]; then
    warn ".env file not found — creating from template"
    cp "$DEPLOY_DIR/.env.production" "$DEPLOY_DIR/.env"
    echo ""
    warn "⚠️  IMPORTANT: Edit .env with your API keys and secrets:"
    warn "   nano $DEPLOY_DIR/.env"
    echo ""
    warn "Required secrets:"
    warn "  - WEBHOOK_SECRET     (generate: python3 -c \"import secrets; print(secrets.token_hex(32))\")"
    warn "  - DASHBOARD_TOKEN    (generate: python3 -c \"import secrets; print(secrets.token_hex(16))\")"
    warn "  - TELEGRAM_BOT_TOKEN (from @BotFather)"
    warn "  - TELEGRAM_CHAT_ID   (from @userinfobot)"
    warn "  - ANTHROPIC_API_KEY  (for RAG AI)"
    warn "  - BINANCE_API_KEY    (optional, dry-run by default)"
    echo ""
    read -p "Press Enter after editing .env to continue (or Ctrl+C to abort)..."
fi

# ── 4. Create user (if needed) ────────────────────────────────
if ! id "trader" &>/dev/null 2>&1; then
    info "Creating 'trader' user..."
    sudo useradd -r -s /sbin/nologin trader
    sudo usermod -aG docker trader
    log "User 'trader' created and added to docker group"
fi

# ── 5. Build & Start ─────────────────────────────────────────
info "Building Docker image..."
docker compose build --no-cache
log "Docker image built successfully"

info "Starting services..."
docker compose up -d
log "Services started"

# ── 6. Install systemd service ────────────────────────────────
if [ -f "$DEPLOY_DIR/deploy/trading-bot.service" ]; then
    info "Installing systemd service..."
    sudo cp "$DEPLOY_DIR/deploy/trading-bot.service" /etc/systemd/system/
    sudo sed -i "s|/opt/trading-bot|$DEPLOY_DIR|g" /etc/systemd/system/trading-bot.service
    sudo systemctl daemon-reload
    sudo systemctl enable trading-bot
    log "Systemd service installed and enabled"
fi

# ── 7. Health Check ──────────────────────────────────────────
info "Waiting for health check..."
sleep 5

MAX_RETRIES=10
for i in $(seq 1 $MAX_RETRIES); do
    if curl -sf http://localhost:5000/health > /dev/null 2>&1; then
        log "Health check passed ✅"
        echo ""
        curl -s http://localhost:5000/health | python3 -m json.tool 2>/dev/null || true
        break
    fi
    if [ "$i" -eq "$MAX_RETRIES" ]; then
        warn "Health check failed after ${MAX_RETRIES} retries"
        warn "Check logs: docker compose logs -f"
    fi
    sleep 3
done

# ── Done ─────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ Deployment Complete!                               ${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""
echo "  🌐 Dashboard:  http://$(hostname -I | awk '{print $1}'):5000/dashboard"
echo "  🔧 Health:     http://$(hostname -I | awk '{print $1}'):5000/health"
echo "  📋 Logs:       docker compose logs -f"
echo "  🔄 Restart:    sudo systemctl restart trading-bot"
echo "  🛑 Stop:       docker compose down"
echo ""
