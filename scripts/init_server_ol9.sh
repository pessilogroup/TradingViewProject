#!/bin/bash
# ═══════════════════════════════════════════════════════
# AUTO INIT SCRIPT CHO ORACLE LINUX 9 (SERVER C)
# Thay thế cho bản Debian 12 do môi trường thực tế là OL9
# Chạy với quyền ROOT: sudo bash init_server_ol9.sh
# ═══════════════════════════════════════════════════════

set -e

echo -e "\n[1/7] Cập nhật hệ thống & Cài package cơ bản (Oracle Linux 9)..."
dnf update -y
# Cài EPEL repo để lấy các package phụ trợ (như fail2ban, htop)
dnf install -y oracle-epel-release-el9 || dnf install -y epel-release
dnf install -y curl wget git htop tmux unzip jq python3 python3-pip sudo tar

echo -e "\n[2/7] Cấu hình Timezone (Asia/Ho_Chi_Minh)..."
timedatectl set-timezone Asia/Ho_Chi_Minh

echo -e "\n[3/7] Cài đặt & cấu hình NTP (Chrony)..."
dnf install -y chrony
cat << 'EOF' > /etc/chrony.conf
server 0.pool.ntp.org iburst
server 1.pool.ntp.org iburst
server time.google.com iburst prefer
server time.cloudflare.com iburst
driftfile /var/lib/chrony/drift
makestep 1.0 3
rtcsync
logdir /var/log/chrony
EOF
systemctl enable --now chronyd

echo -e "\n[4/7] Tạo Swap 2GB (cực kỳ quan trọng cho AI Core)..."
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

echo -e "\n[5/7] Cài đặt Docker & Docker Compose V2 (Bản CentOS/RHEL 9)..."
dnf install -y dnf-plugins-core
dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
mkdir -p /etc/docker
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
systemctl enable --now docker

echo -e "\n[6/7] Cài đặt Tailscale VPN..."
curl -fsSL https://tailscale.com/install.sh | sh
systemctl enable --now tailscaled
echo "Đang kích hoạt Tailscale... (Vui lòng click vào link hiện ra để đăng nhập)"
tailscale up

echo -e "\n[7/7] Cấu hình Firewalld & Fail2Ban..."
dnf install -y fail2ban
cat << 'EOF' > /etc/fail2ban/jail.local
[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 3
[sshd]
enabled = true
port    = ssh
logpath = /var/log/secure
backend = systemd
EOF
systemctl enable --now fail2ban

systemctl enable --now firewalld
firewall-cmd --permanent --add-service=ssh
# Đưa interface tailscale0 vào vùng trusted để VPN thông nhau hoàn toàn
firewall-cmd --permanent --zone=trusted --add-interface=tailscale0
firewall-cmd --reload

echo -e "\n[Hoàn Tất] Oracle Linux 9 VPS đã được thiết lập thành công!"
echo "LƯU Ý: User mặc định hiện tại là opt_admin, sếp hãy cân nhắc thêm user botuser hoặc cấp quyền docker cho opt_admin:"
echo "sudo usermod -aG docker opt_admin"
