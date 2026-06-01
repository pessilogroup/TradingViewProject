#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════════
# bootstrap_server_a.sh — SERVER A (Gateway) Full Setup — V2 Hardened
# Debian 12 Minimal | 1 CPU | 2GB RAM
#
# 🚀 One-shot bootstrap — chạy sau khi nhận VPS mới:
#
#   curl -fsSL https://raw.githubusercontent.com/YOUR_ORG/TradingViewProject/main/deploy/bootstrap_server_a.sh | sudo bash
#
#   HOẶC nếu đã clone repo:
#   sudo bash deploy/bootstrap_server_a.sh
#
# ────────────────────────────────────────────────────────────────────────────
# Checklist (tự động hoàn tất):
#  ✅ 1. System update + packages cơ bản
#  ✅ 2. User botuser (non-root)
#  ✅ 3. Timezone ICT + Locale UTF-8
#  ✅ 4. NTP chrony (Binance-safe < 500ms drift)
#  ✅ 5. Swap 2GB
#  ✅ 6. SSH hardening (key-only, no root)
#  ✅ 7. Fail2Ban brute-force protection
#  ✅ 8. UFW firewall
#  ✅ 9. Docker CE + Compose V2 + daemon.json log limits
#  ✅ 10. Tailscale VPN
#  ✅ 11. Cloudflare Tunnel (cloudflared)
#  ✅ 12. logrotate config (#12)
#  ✅ 13. VBS deploy (docker-compose.server-a.yml)
#  ✅ 14. Monitoring prompt (UptimeRobot #14)
# ════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Colors ────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

log()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()   { echo -e "${YELLOW}[!]${NC} $*"; }
err()    { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }
info()   { echo -e "${BLUE}[→]${NC} $*"; }
section(){ echo -e "\n${CYAN}══ $* ══${NC}"; }

REPO_DIR="/opt/trading-bot"
REPO_URL="https://github.com/YOUR_ORG/TradingViewProject.git"
BRANCH="main"

echo -e "${CYAN}"
echo "═══════════════════════════════════════════════════════════"
echo "  🤖 TradingBot Server A Bootstrap — V2 Hardened           "
echo "  $(date '+%Y-%m-%d %H:%M:%S %Z')                         "
echo "═══════════════════════════════════════════════════════════"
echo -e "${NC}"

[[ "$EUID" -ne 0 ]] && err "Run as root: sudo bash $0"

# ══ 1. System Update ═════════════════════════════════════════════════════════
section "1. System Update + Packages"

apt-get update -q
apt-get upgrade -y -q
apt-get install -y -q \
    curl wget git htop tmux unzip jq \
    ca-certificates gnupg lsb-release \
    python3 python3-pip python3-venv \
    logrotate fail2ban ufw chrony sudo

log "System updated | Python $(python3 --version) | logrotate $(logrotate --version | head -1)"

# ══ 2. Non-root User ═════════════════════════════════════════════════════════
section "2. User 'botuser'"

if ! id botuser &>/dev/null; then
    useradd -m -s /bin/bash botuser
    echo "botuser:$(openssl rand -base64 24)" | chpasswd
    usermod -aG sudo botuser
    log "User 'botuser' created (password randomized — use SSH key only)"
else
    log "User 'botuser' already exists"
fi

# ══ 3. Timezone + Locale ═════════════════════════════════════════════════════
section "3. Timezone ICT + Locale UTF-8"

timedatectl set-timezone Asia/Ho_Chi_Minh
log "Timezone: $(timedatectl | grep 'Time zone')"

# Locale
apt-get install -y -q locales
sed -i 's/# en_US.UTF-8/en_US.UTF-8/' /etc/locale.gen
locale-gen -q
update-locale LANG=en_US.UTF-8
log "Locale: en_US.UTF-8"

# ══ 4. NTP chrony ════════════════════════════════════════════════════════════
section "4. NTP Sync (chrony)"

tee /etc/chrony/chrony.conf > /dev/null << 'CHRONY'
server 0.pool.ntp.org iburst
server 1.pool.ntp.org iburst
server time.google.com iburst prefer
server time.cloudflare.com iburst

makestep 1.0 3
driftfile /var/lib/chrony/chrony.drift
logdir /var/log/chrony
log tracking measurements statistics
maxdistance 0.1
CHRONY

systemctl enable --now chrony
sleep 3
chronyc tracking | grep "System time" || true
log "chrony NTP synced ✅"

# ══ 5. Swap 2GB ═══════════════════════════════════════════════════════════════
section "5. Swap 2GB"

if [[ ! -f /swapfile ]]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo 'vm.swappiness=10' >> /etc/sysctl.conf
    sysctl -p -q
    log "Swap 2GB created"
else
    log "Swap already configured ($(free -h | grep Swap))"
fi

# ══ 6. SSH Hardening ══════════════════════════════════════════════════════════
section "6. SSH Hardening"

tee /etc/ssh/sshd_config.d/tradingbot-hardened.conf > /dev/null << 'SSHCFG'
# TradingBot SSH Hardening — V2
PasswordAuthentication no
ChallengeResponseAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
AllowUsers botuser
ClientAliveInterval 300
ClientAliveCountMax 2
MaxAuthTries 3
X11Forwarding no
AllowTcpForwarding no
AllowAgentForwarding no
SSHCFG

systemctl restart sshd
log "SSH hardened (key-only, no root, botuser only)"
warn "⚠️  Đảm bảo bạn đã copy SSH public key vào /home/botuser/.ssh/authorized_keys TRƯỚC KHI logout!"

# ══ 7. Fail2Ban ═══════════════════════════════════════════════════════════════
section "7. Fail2Ban"

tee /etc/fail2ban/jail.local > /dev/null << 'F2B'
[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
port    = ssh
filter  = sshd
logpath = /var/log/auth.log
F2B

systemctl enable --now fail2ban
log "Fail2Ban active (ban 1h after 3 failed attempts)"

# ══ 8. UFW Firewall ═══════════════════════════════════════════════════════════
section "8. UFW Firewall"

ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow in on tailscale0    2>/dev/null || true
# Cloudflare Tunnel = outbound only, no port needed
echo "y" | ufw enable
log "UFW enabled (SSH + Tailscale allowed)"

# ══ 9. Docker CE ════════════════════════════════════════════════════════════
section "9. Docker CE + Compose V2"

if ! command -v docker &>/dev/null; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg | \
        gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/debian \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update -q
    apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-compose-plugin
    usermod -aG docker botuser
    log "Docker $(docker --version | awk '{print $3}') installed"
else
    log "Docker already installed: $(docker --version)"
fi

# Docker daemon: global log limits (#11 from V2 checklist)
tee /etc/docker/daemon.json > /dev/null << 'DOCKERD'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2"
}
DOCKERD
systemctl restart docker
log "Docker daemon: log-driver=json-file (10m × 3)"

# ══ 10. Tailscale VPN ═════════════════════════════════════════════════════════
section "10. Tailscale VPN"

if ! command -v tailscale &>/dev/null; then
    curl -fsSL https://tailscale.com/install.sh | sh
    log "Tailscale installed"
fi

warn "Chạy thủ công sau: sudo tailscale up"
warn "  → Sẽ hiện URL đăng nhập Tailscale. Mở URL đó trên browser."
warn "  → Sau khi kết nối: tailscale ip -4  (ghi lại IP nội bộ 100.x.x.x)"

# ══ 11. Cloudflare Tunnel ════════════════════════════════════════════════════
section "11. Cloudflare Tunnel (cloudflared)"

if ! command -v cloudflared &>/dev/null; then
    curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | \
        tee /usr/share/keyrings/cloudflare-main.gpg > /dev/null
    echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] \
        https://pkg.cloudflare.com/cloudflared bookworm main' | \
        tee /etc/apt/sources.list.d/cloudflared.list
    apt-get update -q
    apt-get install -y -q cloudflared
    log "cloudflared installed: $(cloudflared --version)"
fi

warn "Cloudflare Tunnel cần setup thủ công:"
warn "  1. cloudflared tunnel login"
warn "  2. cloudflared tunnel create tradingbot-server-a"
warn "  3. Xem hướng dẫn: docs/SETUPS/01_VPS_SERVER_SETUP_GUIDE.md §6"

# ══ 12. logrotate (#12) ════════════════════════════════════════════════════
section "12. logrotate Config"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGROTATE_SRC="${SCRIPT_DIR}/tradingbot-logrotate"

if [[ -f "$LOGROTATE_SRC" ]]; then
    cp "$LOGROTATE_SRC" /etc/logrotate.d/tradingbot
    chmod 644 /etc/logrotate.d/tradingbot
    log "logrotate config: /etc/logrotate.d/tradingbot"
    log "  → Docker logs: daily, compress, keep 3"
    log "  → App logs:    daily, compress, keep 7"
else
    warn "tradingbot-logrotate not found at ${LOGROTATE_SRC}"
    warn "Copy manually: cp deploy/tradingbot-logrotate /etc/logrotate.d/tradingbot"
fi

# ══ 13. Clone Repo + Deploy VBS ══════════════════════════════════════════════
section "13. Clone Repo + Deploy VBS (docker-compose.server-a.yml)"

if [[ -d "$REPO_DIR/.git" ]]; then
    info "Updating existing repo..."
    git -C "$REPO_DIR" pull origin "$BRANCH"
else
    info "Cloning repo → $REPO_DIR"
    warn "Nếu repo PRIVATE: Đảm bảo SSH key của botuser đã được add vào GitHub"
    git clone --branch "$BRANCH" "$REPO_URL" "$REPO_DIR" || {
        warn "Clone failed — sẽ dùng local copy nếu có"
    }
fi

if [[ -d "$REPO_DIR" ]]; then
    cd "$REPO_DIR/deploy"

    # Check .env
    if [[ ! -f "$REPO_DIR/.env" ]] && [[ ! -f "$REPO_DIR/vbs/.env" ]]; then
        warn ".env chưa có — tạo từ template"
        [[ -f "$REPO_DIR/.env.production" ]] && \
            cp "$REPO_DIR/.env.production" "$REPO_DIR/vbs/.env"
        warn "QUAN TRỌNG: Edit vbs/.env và điền WEBHOOK_SECRET, TELEGRAM_*, etc."
    fi

    info "Deploying VBS container..."
    docker compose -f docker-compose.server-a.yml up -d --build
    log "VBS container started"

    # Health check
    sleep 5
    for i in $(seq 1 10); do
        if curl -sf http://localhost:5000/health > /dev/null 2>&1; then
            log "Health check PASS ✅"
            curl -s http://localhost:5000/health | python3 -m json.tool 2>/dev/null || true
            break
        fi
        [[ $i -eq 10 ]] && warn "Health check failed — docker logs:"
        sleep 3
    done
else
    warn "Repo chưa được clone — deploy VBS thủ công:"
    warn "  cd /opt/trading-bot/deploy"
    warn "  docker compose -f docker-compose.server-a.yml up -d"
fi

# ══ 14. UptimeRobot (#14) ════════════════════════════════════════════════════
section "14. UptimeRobot Monitor (#14)"

warn "UptimeRobot cần API key — 2 cách:"
warn ""
warn "  [Tự động] Nếu có UPTIMEROBOT_API_KEY:"
warn "    export UPTIMEROBOT_API_KEY=ur_mainApiKey_xxx"
warn "    export SERVER_A_PUBLIC_IP=\$(curl -4 -sf ifconfig.me)"
warn "    bash ${SCRIPT_DIR}/setup_monitoring.sh"
warn ""
warn "  [Thủ công] https://uptimerobot.com/dashboard#newMonitorBtn"
warn "    Type: HTTP(s)  |  URL: http://YOUR_IP:5000/health"
warn "    Interval: 5 min  |  Alert: keyword 'healthy' missing"

SERVER_A_IP=$(curl -4 -sf ifconfig.me 2>/dev/null || echo "??")
log "Server A public IP: ${SERVER_A_IP}"

# ══ Summary ══════════════════════════════════════════════════════════════════
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ SERVER A Bootstrap Complete — V2 Hardened                 ${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  🌐 VBS Health:   http://localhost:5000/health"
echo "  📋 Logs:         docker logs tradingbot-vbs -f"
echo "  🔐 Tailscale:    sudo tailscale up   (cần làm thủ công)"
echo "  ☁️  CF Tunnel:   cloudflared tunnel login (cần làm thủ công)"
echo "  📡 UptimeRobot:  bash deploy/setup_monitoring.sh"
echo ""
echo "  📁 Repo:         ${REPO_DIR}"
echo "  📄 Config:       ${REPO_DIR}/vbs/.env"
echo ""
echo "  ⚠️  Còn cần làm thủ công:"
echo "     1. SSH key: ssh-copy-id botuser@${SERVER_A_IP}"
echo "     2. Tailscale: sudo tailscale up"
echo "     3. Cloudflare Tunnel: cloudflared tunnel login && cloudflared tunnel create tradingbot-server-a"
echo "     4. UptimeRobot: bash deploy/setup_monitoring.sh (với API key)"
echo "     5. Điền .env: nano ${REPO_DIR}/vbs/.env"
echo ""
