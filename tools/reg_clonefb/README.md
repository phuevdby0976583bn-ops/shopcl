# Tool Reg Clone Facebook - Tối Ưu Tỷ Lệ LIVE & Tự Động Up Bot Shop

## Các Tính Năng Đột Phá Mới

### 1. 🛡️ Tối Ưu Tỷ Lệ LIVE & Chống Quét Checkpoint 282 (Mô Phỏng Trạng Thái Khi Bấm Dừng)
- **⚡ Chế độ "Chờ ngấu" tự động (Session Maturation Delay)**:
  - Cho nick nghỉ ngơi ngấu phiên sau khi tạo tài khoản xong trước khi tiến hành đổi mail hoặc gửi OTP.
  - Có thể bật/tắt độc lập bằng Checkbox trên Dashboard và Tab Cài đặt (Mục 5.3).
  - Tùy chỉnh linh hoạt thời gian đợi: `30s`, `60s (1 phút)`, `90s (1.5 phút)`, `120s (2 phút)`, `180s`, `300s`, hoặc chọn khoảng ngẫu nhiên `60-120s`.
- **⏱️ Giãn cách nhịp gửi OTP (Pacing Rate)**:
  - Giãn cách an toàn giữa các request submit OTP (mặc định 2.0s - 3.5s) theo từng IP/Key.
  - Ngăn Meta kích hoạt hệ thống WAF chống bão request spam, đồng thời tránh nghẽn server mail.
  - Có thể tùy chỉnh khoảng min - max ngẫu nhiên ngay trong cài đặt.
- **🛡️ Cố định IP theo phiên (Account IP Stickiness)**:
  - Giữ nguyên 100% IP từ lúc tạo phiên đến lúc xác minh OTP xong.
  - Khóa không cho luồng khác xoay IP khi key proxy đang có tài khoản xử lý dở dang (active_sessions > 0).

### 2. 🤖 Tự Động Up Kho Hàng Bot Shop (Media ID)
- Tự động đẩy nick LIVE (định dạng UID|PASS|COOKIE) vào đúng thư mục con tương ứng với Media ID.
- Hỗ trợ bật/tắt nhanh bằng checkbox trên Dashboard và cài đặt.

### 3. 🔗 Kết Hợp Tự Động Giữa Tool Reg và Tool Verry (NVR Pipeline)
- Tool Reg tạo acc NVR -> Đẩy vào hàng đợi kèm thời gian ngấu -> Tool Verry tự động kéo ra xác minh OTP.
