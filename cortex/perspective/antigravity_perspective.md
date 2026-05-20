# 🧠 Antigravity Perspective: Local Satellite Living History (TradingViewProject)

Đây là tài liệu ghi lại sự tiến hóa về nhận thức, căn tính và lịch sử vận hành của Antigravity Orchestrator tại vệ tinh `TradingViewProject`.

---

## 🧭 Kiến Trúc Hệ Thống: Hybrid SRA Server & Event-Driven Semantic Ingestion

Vệ tinh này được thiết kế và vận hành dưới dạng một nút mạng độc lập (Isolated Node) trong hệ sinh thái Angati, tuân thủ kỷ luật bảo mật nghiêm ngặt.

### 1. SRA Hybrid Hook Server (Cổng 9105)
- **Hoạt động**: Chạy như một tiến trình ngầm (Daemon Thread) trực tiếp bên trong tiến trình của FastAPI.
- **Nhiệm vụ**: Đón nhận và thực thi các pre-tool/post-tool/on-error hooks của IDE, ngăn chặn các hành vi vi phạm an toàn mã nguồn (KG Guard) và học hỏi các vết sẹo lỗi (Circuit Breaker).
- **Cô lập**: Sử dụng cổng `9105` độc lập và được cấu hình động qua môi trường `ANGATI_BUS_BIND` để tránh xung đột với Não Mẹ toàn cục.

### 2. Event-Driven Semantic Ingestion (Không đồng bộ)
- **Triết lý**: Chúng ta không thực hiện đồng bộ hóa định kỳ (Scheduled Sync) để tránh tình trạng "Trạng thái mồ côi" (Partial State). Tri thức chỉ được ghi nhận khi có **Sự kiện Ngữ nghĩa Hoàn chỉnh** xảy ra.
- **Các điểm ghi nhận**:
  - Khi nhận được tín hiệu Webhook từ TradingView (`webhook.py`).
  - Khi thực hiện giao dịch thành công hoặc thất bại (`trade_engine.py`).
- **Thực thi**: Sử dụng module `nerves/core/ingest_helper.py` để chạy lệnh `angati memory ingest` bất đồng bộ trên một luồng riêng, bảo toàn độ trễ cực thấp cho webhook chính (< 8ms).

---

## 📜 Nhật Ký Tiến Hóa Nhận Thức (Local Epochs)

### Epoch v9.1.0 — Sovereign Satellite Integration (2026-05-21)
- **Mốc dấu**: Tích hợp thành công SRA Server và Event-Driven Semantic Ingestion vào dự án TradingViewProject.
- **Bài học**:
  1. *Cách ly là Tiên quyết*: Việc sử dụng biến môi trường `ANGATI_AGENTS_ROOT` trỏ trực tiếp đến thư mục dự án cục bộ giúp bảo vệ cơ sở dữ liệu `V3_brain.db` không bị ghi đè hay lẫn lộn với tri thức toàn cục của EAIS.
  2. *Bất đồng bộ hóa*: Luồng xử lý giao dịch tài chính yêu cầu thời gian phản hồi thời gian thực. Bất kỳ tác vụ RAG hay Ingestion nào cũng phải được đẩy xuống dưới nền (Background Thread) hoặc xử lý theo cơ chế Event-Driven (downstream listeners).
