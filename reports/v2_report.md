# REPORT v2 — OCR PDF quét bằng Gemini Vision
**Ngày:** 2026-10-26 · **Kế hoạch:** `PLANS_V1-V5.md` mục v2 · **Duyệt code:** `reports/v2_review.md` (3 vòng)

## Tóm tắt
Hoàn thành mục còn nợ của PLANS.md §3.1: PDF quét (không có lớp chữ) giờ được
đọc được khi có khoá Gemini — mỗi trang quét được dựng thành ảnh 150 dpi và gửi
qua Gemini Vision (`gemini-2.5-flash`) để transcribe tiếng Việt giữ cấu trúc dòng.
Không có khoá thì trang quét được **bỏ qua an toàn** kèm cảnh báo — ingestion
không bao giờ đổ vì bản quét.

## Những gì đã làm
1. **`app/ocr.py`** — `extract_pdf_text()`: mỗi trang có lớp chữ (≥20 ký tự) đi
   thẳng; trang quét đi qua hàm OCR (có thể tiêm hàm thay thế để test); trả về
   `(text, warnings)`. `_gemini_ocr_image()` gọi Gemini REST với ảnh base64
   inline + prompt transcribe; lỗi vận chuyển ném `RuntimeError` để tầng trên
   bỏ qua trang một cách có kiểm soát.
2. **`app/ingest.py`** — PDF giờ đi qua `extract_pdf_text`; cảnh báo từng trang
   quét bị bỏ qua được ghi vào `stats["skipped"]` của lần ingest.
3. **`app/main.py`** — tải lên PDF quét mà không có khoá → lỗi HTTP rõ ràng nêu
   nguyên nhân (thay vì lỗi chung chung).
4. **`tests/test_ocr.py`** — 5 test: PDF có lớp chữ không đụng OCR (hàm OCR ném
   AssertionError nếu bị gọi); PDF quét không khoá → bỏ qua an toàn; PDF quét +
   hàm OCR giả → thu hồi đủ văn bản; **hình dạng request Gemini thật** (ảnh PNG
   base64 đúng vị trí `inline_data`, monkeypatch httpx, không gọi mạng); ingest
   báo đúng trang bị bỏ qua (có khôi phục lại dataset sau test).

## Kết quả kiểm chứng
- `python -m pytest tests/ -q` → **41 passed** (36 cũ + 5 mới).
- Bộ đánh giá v1 chạy lại → **10/10 PASS** (không hồi quy).

## Ý nghĩa & hạn chế
- Giờ có thể nạp sách quét thật vào dataset khi có khoá Gemini mà không sửa code.
- Hạn chế trung thực: đường OCR **thật** (gọi Gemini Vision) chưa chạy live trong
  dự án này vì không có khoá — được bao phủ bằng test hình dạng request; khi có
  khoá, nên thử 1 PDF quét thật và ghi nhận vào báo cáo (đã ghi trong kế hoạch).
