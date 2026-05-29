# 📊 Optimized Parameters Matrix: The "Winning Edge"

Bản tổng hợp các bộ tham số tối ưu (Winning Parameters) đã được kiểm chứng qua backtest thực tế trên dữ liệu lịch sử của cặp **BTCUSDT.P (Bybit/Binance)**. Bộ tham số này được thiết kế làm nguồn dữ liệu cấu hình tĩnh cho hệ thống Webhook Server và Auto-Trading Engine.

---

## 🚀 1. CHIẾN LƯỢC 1: MIS V1.6 ( momentum & mean-reversion 1H)
Chiến lược này phù hợp giao dịch chủ động trên khung thời gian nhỏ, lọc tín hiệu qua Trend Template và VCP.

### 📐 Tham số Chỉ báo & Đầu vào (Inputs)
| Nhóm tham số | Tên biến | Giá trị tối ưu | Vai trò & Ý nghĩa |
| :--- | :--- | :---: | :--- |
| **Timeframe** | `timeframe` | **1H (60m)** | Khung thời gian duy nhất sinh lãi ổn định cho chiến lược này. |
| **Trend Template** | `use_tt` | **True** | Bắt buộc kiểm tra 8 tiêu chí xu hướng Minervini. |
| | `rs_bench` | `"BINANCE:BTCUSDT"` | Cặp tiền benchmark để so sánh Relative Strength (RS). |
| **Moving Averages** | `ema_fast` | **20** | EMA nhanh xác định xu hướng ngắn hạn. |
| | `ema_mid` | **50** | EMA trung bình (mốc hỗ trợ động quan trọng). |
| | `ema_slow` | **200** | EMA chậm làm trục xu hướng chính. |
| **RSI Gate** | `rsi_len` | **14** | Độ dài chu kỳ RSI. |
| | `rsi_floor` | **50** | Chỉ enter khi RSI > 50 (mua khi đà tăng mạnh, không mua pullback yếu). |
| **VCP Pivot** | `vcp_lookback` | **20** | Số lượng nến để quét tìm điểm pivot tích lũy (volume dry-up). |
| | `vcp_dry_pct` | **0.6 (60%)** | Khối lượng tại nến Pivot phải < 60% so với Volume MA 50. |
| | `vcp_tight_atr`| **0.7 (70%)** | Biên độ nến Pivot (High - Low) phải hẹp hơn 70% của ATR 14. |
| | `breakout_window`| **15** | Breakout vượt đỉnh Pivot phải xảy ra trong vòng 15 nến kể từ Pivot. |
| **Volume Confirm** | `vol_mult` | **1.5x** | Khối lượng nến breakout phải lớn hơn ít nhất 1.5 lần Volume MA 50. |

### 🛡️ Tham số Quản lý Rủi ro (Risk Management)
| Tên tham số | Giá trị tối ưu | Vai trò & Ý nghĩa |
| :--- | :---: | :--- |
| `risk_pct` | **1.0%** | Rủi ro tối đa trên mỗi deal tính theo vốn chủ sở hữu (Equity). |
| `atr_sl_mul` | **2.0** | Stop-Loss = Entry - (2.0 × ATR 14). |
| `atr_tp_mul` | **8.0** | Take-Profit = Entry + (8.0 × ATR 14) (Tỷ lệ R:R = 4:1 tối ưu cho Crypto). |
| `hard_sl_pct` | **8.0%** | Giới hạn Stop-loss tối đa cố định để tránh biến động quét sâu bất ngờ. |
| `max_pos_pct` | **95.0%** | Tổng quy mô vị thế danh nghĩa tối đa không vượt quá 95% Equity. |
| `use_atr_trail` | **True** | Bật Trailing Stop theo Chandelier (ATR × 3.0) để khóa lợi nhuận. |
| `cooldown_bars` | **3** | Nghỉ 3 nến sau khi đóng lệnh để tránh re-entry vội vã. |

---

## 📈 2. CHIẾN LƯỢC 2: MTT V1.005-B ( trend following DAILY)
Chiến lược giao dịch theo xu hướng dài hạn, tối ưu hóa để ăn các con sóng lớn (Bull Run) và phòng vệ tối đa trong thị trường giá xuống.

### 📐 Tham số Chỉ báo & Đầu vào (Inputs)
| Nhóm tham số | Tên biến | Giá trị tối ưu | Vai trò & Ý nghĩa |
| :--- | :--- | :---: | :--- |
| **Timeframe** | `timeframe` | **1D (Daily)** | Khung thời gian vĩ mô, lọc sạch 99% nhiễu Crypto. |
| **MA Setup** | `ma_type` | **"EMA"** | **EMA vượt trội SMA** về mặt tốc độ phản ứng (Win Rate 54% vs 44%). |
| | `fast_len` | **20** | EMA 20. |
| | `med_len` | **50** | EMA 50. |
| | `slow_len` | **100** | EMA 100 (V1.005 tuning chọn EMA 100 thay vì EMA 200 vì EMA 200 quá trễ). |

### 🛡️ Quy mô lệnh (Profile Sizing - Không Đòn Bẩy)
| Profile | Tỷ lệ quy mô (% Equity) | Ghi chú vận hành |
| :--- | :---: | :--- |
| **Spot** | **10.0%** | Đầu tư dài hạn giao dịch Spot, tối đa 1 vị thế. |
| **Margin** | **20.0%** | Ký quỹ (tương đương quy mô danh nghĩa 60% với đòn bẩy thực tế 3x). |
| **Futures** | **10.0%** | Hợp đồng tương lai (tương đương quy mô danh nghĩa 100% với đòn bẩy thực tế 10x). |

### 🚦 Quy tắc Kích hoạt Lệnh (Execution Rules)
- **Long Entry (Bull Start)**: Khi `EMA 20 > EMA 50 > EMA 100` bắt đầu xếp chồng song song (Bull Stack).
- **Long Exit (Bull End)**: Khi cấu trúc xếp chồng bị phá vỡ (`EMA 20 < EMA 50` hoặc `EMA 50 < EMA 100`).
- **Breakout Long Signal (Hỗ trợ từ Short)**: Khi Bear Stack (`EMA 20 < EMA 50 < EMA 100`) chính thức kết thúc, phát tín hiệu cảnh báo có khả năng thị trường đảo chiều sang tăng mạnh (Breakout Long từ đáy).

---

## 📑 3. MA TRẬN KẾT QUẢ BACKTEST THỰC TẾ (SO SÁNH)

| Chiến lược | Khung thời gian | Giai đoạn test | Số lệnh | Win Rate | Profit Factor | Max Drawdown | Hiệu suất |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **MIS v1.6** | 1H | 6 năm (2020-2026) | 11 | **81.82%** | **3.539** | 16.15% | **+48.21%** |
| **MTT v1.005-b** | Daily | 6 năm (2020-2026) | 13 | **53.85%** | **7.145** | **2.99%** | **+53.45%** |

> [!TIP]
> **Nhận định thực chiến**:
> - MTT v1.005-b (Daily) có tỷ lệ **Profit Factor cực cao (7.145)** và **Drawdown cực thấp (2.99%)**, là chiến lược lý tưởng để tích lũy tài sản dài hạn.
> - MIS v1.6 (1H) đòi hỏi hệ thống webhook hoạt động liên tục 24/7 để nhận các tín hiệu hiếm nhưng cực kỳ chính xác.
