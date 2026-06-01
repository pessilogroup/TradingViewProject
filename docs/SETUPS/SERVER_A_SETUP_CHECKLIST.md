# 📋 Server A Setup Progress Checklist

Dựa trên tài liệu [SERVER_A_SETUP_PROMPT.md](file:///c:/Users/Son/TRADING_CLONE/docs/SETUPS/SERVER_A_SETUP_PROMPT.md) và trạng thái kiểm tra hệ thống thực tế trên VPS `103.82.21.77` của anh Son, đây là bảng theo dõi tiến độ chi tiết:

---

## 🟢 PHẦN 1: ĐÃ HOÀN THÀNH (DONE)

### ⚡ BƯỚC 0: Chuẩn bị thông tin trước
* [x] **VPS đã mua:** Đang chạy VPS Debian 12 Bookworm tại IP `103.82.21.77` (1 CPU Xeon E5-2690 v4, 2GB RAM, 40GB Disk).
* [x] **SSH Access:** Đã cấu hình và kết nối thành công qua SSH Key chuyên dụng `id_ed25519_trading`.

### ⚡ BƯỚC 1: SSH Vào VPS & Cập Nhật
* [x] **Cập nhật hệ thống:** Đã cập nhật gói hệ thống.
* [x] **Cài đặt công cụ cơ bản:** Đã cài đặt `curl`, `wget`, `git`, `htop`, `tmux`, `jq`, `ca-certificates`, `gnupg`, `lsb-release`, `python3`, `python3-pip`, `python3-venv`, `sudo`, `locales`, `chrony`, `fail2ban`, `ufw`.

### ⚡ BƯỚC 2: Tạo User + SSH Hardening
* [x] **Tạo user:** Đã tạo user non-root `botuser` với thư mục `/home/botuser` và quyền `sudo`.
* [x] **SSH Key Link:** Đã cấu hình liên kết thành công SSH Public Key mới vào `authorized_keys` của `botuser`.

### ⚡ BƯỚC 3: Timezone + NTP + Swap
* [x] **Timezone:** Đã đồng bộ sang múi giờ Việt Nam (`Asia/Ho_Chi_Minh`).
* [x] **NTP (Chrony):** Đã kích hoạt chrony. Trạng thái `System time` cực kỳ hoàn hảo (`0.0005 seconds fast of NTP time`).
* [x] **Swap 2GB:** Đã tạo và kích hoạt Swap file 2GB (`2.0Gi` trống hoàn toàn) để phòng chống tràn RAM (OOM).

### ⚡ BƯỚC 4: Firewall + Fail2Ban
* [x] **Fail2Ban:** Đã cài đặt và kích hoạt bảo vệ chống brute force SSH.
* [x] **UFW Firewall:** Đã cài đặt, cấu hình chặn mặc định incoming, cho phép outgoing và cho phép SSH cổng mặc định.

### ⚡ BƯỚC 5: Docker & Docker Compose
* [x] **Cài đặt Docker GPG Key & Repo:** Đã cài đặt kho lưu trữ Docker.
* [x] **Cài đặt Docker CE & Docker Compose Plugin:** Đã cài đặt và chạy daemon.
* [x] **Cấu hình log rotation cho Docker daemon:** Đã set limits trong `daemon.json` (`max-size: 10m`, `max-file: 3`).
* [x] **Kiểm tra docker container:** VBS container đã up và chạy bình thường.

### ⚡ BƯỚC 6: Tailscale VPN (Mạng ảo nội bộ)
* [x] **Cài đặt Tailscale và chạy `sudo tailscale up`:** Đã cài đặt và xác thực.
* [x] **Ghi lại IP Tailscale:** Server A có IP Tailscale là `100.92.13.100`.

### ⚡ BƯỚC 7: Cloudflare Tunnel (Expose HTTPS không mở port)
* [x] **Cài đặt `cloudflared` daemon:** Đã cài đặt `/usr/local/bin/cloudflared`.
* [x] **Chạy `cloudflared tunnel login` và authorize domain:** Đã liên kết domain `utopiavn.co`.
* [x] **Tạo tunnel `trading-gateway` và cấu hình file `/etc/cloudflared/config.yml`:** Tự động định tuyến qua `trading.utopiavn.co`.
* [x] **Cấu hình DNS trỏ subdomain về tunnel:** Đã trỏ subdomain `trading.utopiavn.co` về tunnel `7b3b80b2-15ec-4f8f-9426-6c1dbeba3e3c`.
* [x] **Cài đặt service auto-start cho cloudflared:** Service systemd `cloudflared.service` đang chạy cực kỳ ổn định.

### ⚡ BƯỚC 8: Deploy VPS Buffer Service (VBS)
* [x] **Copy thư mục vbs/ và file docker-compose.vbs.yml** từ máy Local lên `/home/botuser/` trên VPS.
* [x] **Tạo file cấu hình vbs/.env** (sử dụng mã `BUFFER_SECRET` được chỉ định).
* [x] **Khởi chạy VBS qua Docker Compose:** Container `botuser-vbs-1` hoạt động 24/7 trên port 5000 (nội bộ).

### ⚡ BƯỚC 9: Verify & Smoke Test
* [x] **Gọi `/health` nội bộ tại cổng `5000`:** Thành công, trả về trạng thái `healthy`, `db: ok`.
* [x] **Gọi `/health` qua HTTPS Cloudflare Tunnel công khai:** Hoạt động tốt và bảo mật.
* [x] **Thử đẩy tín hiệu mẫu (`POST /ingest`) bằng lệnh `curl`:** Đã test thành công đẩy tín hiệu BTCUSDT và được xếp hàng đợi (Queue ID #1).
* [x] **Thử gọi API kéo tín hiệu (`GET /consume` & `POST /ack`):** Bot local đã giả lập thành công việc kéo tín hiệu (consume) và xác nhận (ack) xử lý thành công.

---

## 🟢 PHẦN 2: HOÀN THÀNH 100% - KHÔNG CÒN BƯỚC PENDING nào!

---

## 🔑 Bảng Ghi Nhớ Tham Số Cho Các Bước Tiếp Theo
* **Server A Public IP:** `103.82.xx.xx` (Username: `botuser`)
* **Server A Tailscale IP:** `100.92.13.100` (Hostname: `server-a-gateway`)
* **Public Domain Tunnel:** `https://trading.utopiavn.co`
* **Mật khẩu sudo tạm thời:** `TradingBot2026!`
* **Mã khóa BUFFER_SECRET (đã sinh):** `9ea7c89fbfd63a8a2bc8644e99da54fc5b2c7e098fe1d9e2b10a4e320f781a7b`
