# REVIEW v2 — OCR PDF quét bằng Gemini Vision
**Ngày:** 2026-10-26 · **Phạm vi:** `app/ocr.py`, `app/ingest.py`, `app/main.py` (upload), `tests/test_ocr.py`

---

## Vòng 1 — sau khi triển khai xong
**Kiểm chứng:** chạy `tests/test_ocr.py` → 2/5 fail.

**Phát hiện (lỗi thật, đã sửa):**
1. Test dựng PDF bằng `insert_textbox` với font mặc định (base-14) → dấu tiếng
   Việt thành `?` trong lớp chữ, làm fail assertion nội dung. Sửa: dựng PDF bằng
   `insert_htmlbox` (nhúng chữ Unicode thật).
2. Test monkeypatch `ocr_mod.keys` — nhưng `keys` được import *bên trong* hàm nên
   thuộc tính không tồn tại ở mức module. Sửa: patch trực tiếp `app.keys.get_api_key`.
3. Helper `_make_blank_page` trả về page sau khi tài liệu đã đóng → PyMuPDF lỗi
   null reference khi render. Sửa: render PNG ngay trong ngữ cảnh mở.

## Vòng 2 — sau khi sửa vòng 1
**Kiểm chứng:** `tests/test_ocr.py` 5/5 xanh, **nhưng** toàn bộ suite fail 4 test:
`test_retrieve` bị ảnh hưởng (bảng chunks rỗng).

**Phát hiện (hồi quy do test mới gây ra, đã sửa):**
- `test_ingest_reports_skipped_scanned_pages` gọi `ingest.ingest(tmp_path)` —
  theo thiết kế ingest **xóa toàn bộ bảng chunks rồi dựng lại**, nên suite dùng
  chung database bị mất dữ liệu dataset. Sửa: bọc `try/finally` và re-ingest
  dataset thật sau khi test xong. Sau sửa: **41/41 xanh**.

## Vòng 3 — duyệt chốt
**Kiểm chứng:** `pytest` 41/41; bộ đánh giá v1 vẫn **10/10** (không hồi quy chất lượng).

**Phát hiện (cải thiện nhỏ, đã làm):**
- Tải lên PDF quét khi không có khoá Gemini trước đây trả lỗi chung chung
  "Hãy dán nội dung…" — giờ `_extract_upload` phát hiện trường hợp này và báo
  rõ: "Tệp PDF là bản quét và chưa có khoá Gemini để OCR".

**Kết luận:** không còn lỗi. Chốt v2.
