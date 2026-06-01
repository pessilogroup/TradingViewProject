#!/bin/bash
# ═══════════════════════════════════════════════════════
# AUTO INIT SCRIPT CHO DEBIAN 12 (SERVER A & SERVER C)
# Dựa theo 01_VPS_SERVER_SETUP_GUIDE.md
# Chạy với quyền ROOT: bash init_server_debian.sh
# ═══════════════════════════════════════════════════════

set -e

echo -e "\n[1/7] Cập nhật hệ thống & Cài package cơ bản..."
apt update && apt upgrade -y
apt install -y curl wget git htop tmux unzip jq ca-certificates gnupg lsb-release python3 python3-pip python3-venv sudo

echo -e "\n[2/7] Cấu hình Timezone (Asia/Ho_Chi_Minh)..."
timedatectl set-timezone Asia/Ho_Chi_Minh
apt install -y locales
sed -i 's/# en_US.UTF-8/en_US.UTF-8/' /etc/locale.gen
locale-gen
update-locale LANG=en_US.UTF-8

echo -e "\n[3/7] Cài đặt & cấu hình NTP (Chrony)..."
apt install -y chrony
cat << 'EOF' > /etc/chrony/chrony.conf
server 0.pool.ntp.org iburst
server 1.pool.ntp.org iburst
server time.google.com iburst prefer
server time.cloudflare.com iburst
makestep 1.0 3
driftfile /var/lib/chrony/chrony.drift
logdir /var/log/chrony
log tracking measurements statistics
maxdistance 0.1
EOF
systemctl enable --now chrony

echo -e "\n[4/7] Tạo Swap 2GB..."
if ! grep -q swapfile /etc/fstab; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo 'vm.swappiness=10' >> /etc/sysctl.conf
    sysctl -p
else
    echo "Swap đã tồn tại."
fi

echo -e "\n[5/7] Cài đặt Docker & Docker Compose..."
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg || true
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
cat << 'EOF' > /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2"
}
EOF
systemctl restart docker

echo -e "\n[6/7] Cài đặt Tailscale VPN..."
curl -fsSL https://tailscale.com/install.sh | sh
# Kích hoạt Tailscale (User sẽ cần click link)
echo "Đang kích hoạt Tailscale... (Vui lòng click vào link hiện ra để đăng nhập)"
tailscale up

echo -e "\n[7/7] Cài đặt UFW Firewall & Fail2Ban..."
apt install -y ufw fail2ban
# Cấu hình Fail2Ban
cat << 'EOF' > /etc/fail2ban/jail.local
[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 3
[sshd]
enabled = true
port    = ssh
filter  = sshd
logpath = /var/log/auth.log
EOF
systemctl enable --now fail2ban

# Cấu hình UFW
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow in on tailscale0
echo "y" | ufw enable

echo -e "\n[Hoàn Tất] VPS đã được thiết lập nền tảng cơ bản!"
echo "LƯU Ý QUAN TRỌNG TIẾP THEO: Hãy tạo user 'botuser' và khoá SSH Root theo tài liệu."
