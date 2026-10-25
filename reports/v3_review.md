# REVIEW v3 — Đăng nhập nhiều người dùng + sao lưu
**Ngày:** 2026-10-26 · **Phạm vi:** `app/auth.py`, `app/backup.py`, `app/db.py` (migration), `app/main.py` (middleware + 5 endpoint + phân quyền), UI (`templates/`, `static/`), `tests/test_auth_backup.py`

---

## Vòng 1 — sau khi triển khai xong
**Kiểm chứng:** chạy `tests/test_auth_backup.py` → treo/ghi nhận lỗi.

**Phát hiện (lỗi thật, đã sửa):**
1. **Xoá đụng khoá ngoại ở cleanup test:** `_reset_auth_state()` DELETE users trong
   khi conversation tham chiếu user → `IntegrityError` (đây cũng là nguồn gốc việc
   test "treo" ở lần chạy đầu — luồng dừng ở teardown giữa chừng). Sửa: xoá theo
   thứ tự phụ thuộc (run_rounds → … → conversations → sessions → users) rồi cài
   lại user sentinel.
2. **Rotation backup sai (bắt được bởi test):** 5 lần backup trong cùng 1 giây trùng
   tên tệp (stamp chỉ tới giây) → ghi đè, chỉ còn 1 tệp thay vì giữ đúng 3. Sửa:
   stamp kèm microgiây.
3. *(dọn code)* bản nháp `auth.create_user` còn logic rối "placeholder" không dùng
   → đơn giản hoá: hàm chỉ tạo user, endpoint quyết định ai được phép gọi.

## Vòng 2 — sau khi sửa vòng 1
**Kiểm chứng:** `tests/test_auth_backup.py` 4/4 xanh; toàn suite **45/45**; bộ
đánh giá v1 vẫn **10/10**.

**Xác nhận thiết kế:**
1. Chế độ mở: chưa có tài khoản → mọi API chạy như trước (sentinel user `shared`
   giữ khoá ngoại + làm chủ dữ liệu cũ).
2. `/api/setup` "nhận" chính dòng sentinel làm tài khoản đầu → **dữ liệu chế độ mở
   không mồ côi** khi bật đăng nhập.
3. Phân quyền: middleware chặn `/api/*` (trừ setup/login/me/static) khi auth bật;
   documents/versions/diff/downloads đều qua `_own_document`/`_own_version` join
   theo `user_id` — người khác nhận 404 (không lộ tồn tại).

## Vòng 3 — duyệt chốt
**Kiểm chứng trên trình duyệt thật** (uvicorn :8090, luồng đầy đủ):
chế độ mở tra cứu 200 → tab Cài đặt tạo tài khoản "coCham" ("Đã bật đăng nhập —
tài khoản này sở hữu toàn bộ dữ liệu hiện có") → đăng xuất → `/api/conversations`
= **401**, **màn hình đăng nhập hiện ra** (có ô mật khẩu) → đăng nhập đúng →
overlay biến mất, API 200 trở lại, `/api/me` = coCham.

**Phát hiện nhỏ (đã sửa trong vòng):** README thiếu hướng dẫn đăng nhập/sao lưu và
lệnh `schtasks` đặt lịch backup như đã hứa trong kế hoạch → bổ sung đủ.

**Kết luận:** không còn lỗi. Chốt v3.
