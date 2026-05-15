---
name: minervini-assess
description: Phân tích nhanh chart hiện tại theo phương pháp SEPA của Mark Minervini. Đọc symbol/indicator/quote qua MCP tradingview, tham chiếu Minervini KB local, sinh nhận xét ngắn gọn. Dùng khi user gõ /minervini-assess hoặc hỏi "đánh giá chart này theo Minervini".
---

# Minervini SEPA Quick Assessment

Sinh phân tích SEPA cho chart TradingView đang mở — **dùng trực tiếp phiên Claude Code (không tốn API credit).**

## Bước thực hiện

1. **Đọc trạng thái chart hiện tại** qua MCP tradingview (chạy song song):
   - `mcp__tradingview__chart_get_state` → symbol, timeframe, danh sách indicator
   - `mcp__tradingview__quote_get` → giá realtime
   - `mcp__tradingview__data_get_study_values` → giá trị RSI/MA/MACD hiện tại

2. **Nếu user cung cấp symbol khác** trong `$ARGUMENTS`, chuyển chart trước:
   - `mcp__tradingview__chart_set_symbol` với symbol đó.

3. **Truy vấn Minervini KB** (chunks tại `docs/knowledge/trading_wizard/`):
   - Dùng Grep/Glob để tìm chunk liên quan tới pattern phát hiện (VCP, Trend Template, Stage 2, breakout volume...).
   - Đọc 1-2 chunk phù hợp nhất.

4. **Sinh phân tích** theo cấu trúc dưới (≤200 từ, có emoji cho Telegram-friendly):
   - 📊 **Chất lượng tín hiệu**: Mạnh / Trung bình / Yếu + lý do
   - ✅ **Điểm phù hợp Minervini**: Trend Template? VCP? Volume?
   - 🎯 **Khuyến nghị**: Mua / Bán / Chờ + stop-loss gợi ý
   - ⚠️ **Rủi ro** (nếu có)

## Yêu cầu

- Nếu MCP tradingview không phản hồi → nhắc user chạy `/tv-start`.
- Không bịa giá trị indicator — luôn lấy từ MCP.
- File chunk Minervini ở: `docs/knowledge/trading_wizard/chunks/`.
