# REVIEW v1 — Bộ đánh giá chất lượng + requirements.txt
**Ngày:** 2026-10-26 · **Phạm vi:** `app/evaluate.py`, `eval/` (10 ca), `scripts/make_eval.py`, `tests/test_evaluate.py`, `requirements.txt`, README

Quy ước: mỗi vòng duyệt = chạy kiểm chứng + soi lại code; có lỗi thì sửa ngay rồi duyệt lại vòng tiếp theo. Chỉ chốt phiên bản khi vòng cuối không còn lỗi.

---

## Vòng 1 — sau khi triển khai xong
**Kiểm chứng:** `pytest` 36/36 xanh; `python -m app.evaluate` đạt **10/10 ca**.

**Phát hiện (2 lỗi, đã sửa):**
1. `app/evaluate.py` có vòng lặp `for file_field in (...)` nhưng biến lặp không
   dùng đến — hai trường tệp được kiểm tra bằng `all(...)` gọn hơn. → Đã viết lại.
2. Thư mục `data_eval/` (chạy thử) chưa nằm trong `.gitignore` (chỉ liệt kê từng
   thư mục data cụ thể). → Đổi thành mẫu `data*/` che mọi biến thể.
3. *(cải thiện)* README thiếu hướng dẫn chạy bộ đánh giá và `requirements.txt`. →
   Bổ sung mục "Bộ đánh giá chất lượng" và "Cài đặt".

## Vòng 2 — sau khi sửa vòng 1
**Kiểm chứng:** `pytest` 36/36 xanh lần nữa; eval chạy lại **10/10**; `python -m
app.evaluate --help` hoạt động.

**Phát hiện (không lỗi mới, 2 xác nhận):**
1. Provider mặc định của eval khi không có khoá: `keys.get_default_provider()`
   rơi về `config.DEFAULT_PROVIDER` = `mock` khi không có `GEMINI_API_KEY` — CI
   không cần khoá vẫn chạy được. Xác nhận đúng chủ đích.
2. Phân bố bộ đánh giá: 3 môn (Toán/Tiếng Việt/Tiếng Anh), 5 khối (1,2,3,4,5),
   đủ 2 loại tài liệu; 5/10 ca **có** từ khoá gốc SGK để kiểm tra bám sát nội
   dung, 5/10 ca không có dữ liệu dataset (kiểm tra đường không-trích-dẫn hoạt
   động an toàn). Xác nhận đa dạng đúng như kế hoạch.

## Vòng 3 — duyệt chốt
**Kiểm chứng:** `pytest` 36/36; `git status` sạch (không tệp rác, `data*/` bị
ignore đúng); không có bí mật/khoá trong các tệp mới.

**Kết luận:** không còn lỗi. Chốt v1.
