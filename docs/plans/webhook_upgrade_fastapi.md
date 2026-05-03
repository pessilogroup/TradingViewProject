# Kế hoạch Nâng cấp TradingView Webhook (Auto-Pilot Sprints)

Dựa trên yêu cầu, quá trình nâng cấp hệ thống Webhook được chia thành các **Sprint** rõ ràng để đảm bảo hệ thống chuyển đổi từ một Webhook thử nghiệm (Flask) thành một **Trading Bot Production-Ready** với hiệu năng cao (Async), bảo mật chặt chẽ và đầy đủ cảnh báo.

## Quyết định (Decision Log)

**Về vấn đề Thông báo (Notifications) - Trực tiếp vs OpenClaw:**
**Khuyến nghị:** Tích hợp **TRỰC TIẾP** (Direct Integration) tại đây. 
*Lý do:* Hệ thống Trading yêu cầu độ trễ (latency) thấp nhất có thể. Việc gửi trực tiếp một HTTP Request bất đồng bộ (async) đến Telegram/Discord từ con bot này sẽ mất chưa tới 0.1 giây và không có điểm lỗi trung gian (single point of failure). Nếu đẩy qua OpenClaw, bạn sẽ phải tốn thêm thời gian serialize message, duy trì worker, và tăng rủi ro delay lệnh. Mình sẽ code một module Notification cực kỳ gọn nhẹ ở ngay trong `server/`.

---

## Phân bổ Sprints

### Sprint 1: Async Refactoring & Security Hardening (FastAPI)
Thay vì dùng Flask chặn luồng (blocking), chuyển sang **FastAPI** để đạt tốc độ xử lý hàng ngàn tín hiệu mỗi giây mà không treo máy.

- Cài đặt `fastapi`, `uvicorn`, `aiohttp`.
- Viết lại hàm nhận Webhook bằng `async def webhook()`.
- **IP Whitelisting:** Code thêm một Middleware kiểm tra IP. Chỉ cho phép các IP của TradingView (`52.89.214.238`, `34.212.75.30`, `54.218.53.128`, `52.32.178.7`) được phép đi qua. Nếu kết hợp cùng `WEBHOOK_SECRET` sẽ tạo thành lớp bảo mật kép cực kỳ an toàn.

### Sprint 2: Dynamic Order Sizing & Robust Execution
Loại bỏ việc hardcode lệnh mua 10 USDT, cho phép linh hoạt từ biểu đồ.

- Đọc thêm tham số `size` hoặc `quoteOrderQty` từ JSON payload của TradingView.
- Viết lại hàm `_place_binance_order` thành `async def` (dùng `aiohttp` thay cho `requests`).
- Thêm khối lệnh `try...except` để bắt lỗi khi Binance từ chối lệnh (ví dụ: Không đủ số dư, API Key hết hạn).

### Sprint 3: Real-time Notifications (Telegram / Discord)
Gửi báo cáo khớp lệnh ngay tức khắc.

- Tạo file `server/notifier.py` chứa các hàm `async def send_telegram_alert(message)`.
- Hàm này sẽ được gọi ở chế độ chạy nền (background task) trong `main.py` ngay sau khi Binance trả về kết quả, báo cáo rõ: **"Đã Mua BTCUSDT | Khối lượng: 50 USDT | Giá: 68,000 | Tình trạng: Thành công"**.
- Cập nhật `server/config.py` để lấy `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` từ biến môi trường.

---

## Các Bước Triển Khai (Brainstorming & Execution)
(Các chi tiết kỹ thuật sẽ được cập nhật liên tục vào đây trong quá trình Auto-Pilot).
