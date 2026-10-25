# REVIEW v4 — Phục hồi phiên bản (rollback) + quản lý hội thoại
**Ngày:** 2026-10-26 · **Phạm vi:** `app/main.py` (restore + soft-delete + lọc danh sách), `app/db.py` (cột `deleted_at`), UI (`templates/`, `static/`), `tests/test_rollback.py`

---

## Vòng 1 — sau khi triển khai xong
**Kiểm chứng:** `tests/test_rollback.py` → 2/3 fail.

**Phát hiện (lỗi thật, đã sửa):**
1. **Teardown vi phạm khoá ngoại lần nữa** (tệp test mới lặp lại sai y hệt v3:
   `DELETE FROM users` khi conversations còn tham chiếu). Lỗi này còn *giữ khoá
   ghi* làm test kế tiếp chết vì "database is locked". Sửa: đưa cleanup chuẩn về
   `conftest.reset_auth_state()` (xoá theo thứ tự phụ thuộc + rollback khi lỗi),
   cả hai tệp test dùng chung.
2. Trong quá trình sửa, phát hiện mình vừa **xé mất decorator** `@app.get(...diff)`
   khi chèn endpoint mới vào trước nó (hàm `document_diff` thành hàm thường —
   endpoint /diff trả 404). Sửa: khôi phục decorator; thêm nhận thức: khi chèn
   code theo "anchor line", phải giữ nguyên anchor.

## Vòng 2 — sau khi sửa vòng 1
**Kiểm chứng:** `test_rollback` + `test_auth_backup` 7/7; toàn suite **48/48**;
eval v1 **10/10**.

**Xác nhận hành vi:**
- Restore kiểu **không phá vỡ**: nội dung v cũ thành v mới (v+1), ghi chú
  "Phục hồi từ v1", có đủ tệp docx/pdf, hội thoại ghi lại hành động; diff giữa
  bản phục hồi và bản nguồn = rỗng.
- Người dùng khác restore phiên bản không phải của mình → 404.
- Xoá hội thoại: ẩn khỏi danh sách, dòng DB còn (`deleted_at`), tài liệu vẫn
  truy cập được trực tiếp.

## Vòng 3 — duyệt chốt (trên trình duyệt thật)
**Phát hiện (1 lỗi UI thật, đã sửa):**
- Tạo tài liệu → chỉnh sửa thành v2 → chọn v1: **nút "↩ Phục hồi" không hiện**.
  Nguyên nhân: logic hiển thị nút đặt trong `openDocument` (chạy 1 lần khi mở
  tài liệu) thay vì `showVersion` (chạy mỗi lần đổi phiên bản) → không cập nhật
  theo lựa chọn dropdown. Sửa: chuyển 2 dòng điều kiện vào `showVersion`.
  Kiểm lại trên trình duyệt: chọn bản mới nhất → nút ẩn; chọn v2 → nút hiện;
  luồng restore tạo đúng v3 "Phục hồi từ v1"; nút xoá hội thoại có trên từng
  dòng Lịch sử.

**Kết luận:** không còn lỗi. Chốt v4.
