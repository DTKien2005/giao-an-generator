# REPORT v3 — Đăng nhập nhiều người dùng + sao lưu
**Ngày:** 2026-10-26 · **Kế hoạch:** `PLANS_V1-V5.md` mục v3 · **Duyệt code:** `reports/v3_review.md` (3 vòng)

## Tóm tắt
Hoàn thành phần còn nợ của Phase 6: **đăng nhập bật tiến bộ** (app chạy mở như
trước cho tới khi tài khoản đầu tiên được tạo) và **sao lưu dữ liệu** bằng một
lệnh. Thiết kế "nhận tài khoản" bảo đảm toàn bộ dữ liệu tạo trong chế độ mở vẫn
thuộc về người dùng đầu tiên — không mồ côi dữ liệu khi bật khoá.

## Những gì đã làm
1. **`app/auth.py`** — băm mật khẩu PBKDF2-HMAC-SHA256 (240.000 vòng, salt riêng
   từng user), phiên token ngẫu nhiên lưu bảng `sessions` (hạn 7 ngày),
   `setup_first_user()` nhận dòng user sentinel làm tài khoản đầu.
2. **`app/db.py`** — cột `password_hash` (migration `ALTER TABLE` cho DB cũ),
   bảng `sessions`, sentinel `shared` cho chế độ mở.
3. **`app/main.py`** — middleware chặn API khi auth bật (trừ setup/login/me/
   static); `POST /api/setup|login|logout|users`, `GET /api/me`; mọi truy vấn
   dữ liệu lọc theo `user_id`; documents/versions/diff/download kiểm tra quyền
   sở hữu (người khác nhận 404 — không lộ tài nguyên).
4. **UI** — overlay "Đăng nhập" tự hiện khi khóa; tab Cài đặt có thẻ "Tài khoản"
   (tạo tài khoản đầu / đăng xuất); mọi fetch xử lý 401 bằng cách hiện overlay.
5. **`app/backup.py`** — `python -m app.backup`: zip database (chụp qua SQLite
   backup API — nhất quán khi đang chạy), thư mục generated/uploads và khoá mã
   hoá; giữ 10 bản gần nhất; README kèm lệnh `schtasks` đặt lịch hằng ngày.
6. **`tests/test_auth_backup.py`** — 4 test: chế độ mở; toàn bộ luồng
   setup→khóa→sai mật khẩu→2 người dùng cô lập (không thấy tài liệu của nhau)→
   đăng xuất; thuộc tính băm (salt riêng, chống so khớp sai); backup + rotation.

## Kết quả kiểm chứng
- `python -m pytest tests/ -q` → **45 passed** (41 cũ + 4 mới).
- Bộ đánh giá v1 → **10/10 PASS** (không hồi quy).
- Trình duyệt thật: bật đăng nhập, khóa 401, overlay, đăng nhập lại thành công
  (chi tiết ở `reports/v3_review.md` vòng 3).

## Ý nghĩa & hạn chế
- App giờ đủ an toàn để mở ra ngoài laptop (qua Cloudflare Tunnel ở v5) mà không
  sợ người lạ đọc/xoá tài liệu.
- Hạn chế: chưa có "quên mật khẩu" (app cục bộ — tự xoá DB users để reset, ghi
  trong README nếu cần); rate limit vẫn theo IP, chưa theo user.
