# REPORT v1 — Bộ đánh giá chất lượng + requirements.txt
**Ngày:** 2026-10-26 · **Kế hoạch:** `PLANS_V1-V5.md` mục v1 · **Duyệt code:** `reports/v1_review.md` (3 vòng)

## Tóm tắt
Version này trả nợ mục cuối của Phase 1 trong `PLANS.md`: một bộ đánh giá chạy
được để đo chất lượng pipeline trước khi làm các tính năng lớn (v2–v5), cùng
`requirements.txt` để khoá môi trường (chuẩn bị cho CI ở v5).

## Những gì đã làm
1. **`eval/` — 10 ca đánh giá gốc** (không dính bản quyền): lớp 1–5, môn Toán /
   Tiếng Việt / Tiếng Anh, đủ giáo án lẫn phiếu bài tập. Mỗi ca gồm yêu cầu
   (`*_request.json`) và kỳ vọng (`*_expected.json`: mục bắt buộc, từ khoá gốc
   SGK nếu có, tổng thời lượng hoạt động, độ dài đáp án).
2. **`app/evaluate.py`** — chạy pipeline trên từng ca rồi chấm bằng **rubric xác
   định** (không dùng LLM chấm): đủ mục theo định dạng; nội dung bám từ khoá
   trích dẫn SGK; tổng thời lượng 30–45 phút; đáp án đủ dài; văn bản có dấu
   tiếng Việt; tệp docx/pdf tồn tại. CLI: `python -m app.evaluate`.
3. **`tests/test_evaluate.py`** — 3 test: bộ đủ 10 ca & đa dạng; chạy trọn bộ
   đạt 10/10 với mock; rubric bắt được lỗi cấu trúc/thời lượng/thiếu dấu.
4. **`requirements.txt`** — khoá dải phiên bản các thư viện đang dùng.
5. README bổ sung cách chạy đánh giá và cài đặt.

## Kết quả kiểm chứng
- `python scripts/make_eval.py` → 10 ca được tạo.
- `python -m app.evaluate` (mock) → **10/10 ca PASS**.
- `python -m pytest tests/ -q` → **36 passed** (33 cũ + 3 mới, không hỏng gì).

## Ý nghĩa & hạn chế
- Từ v2, mỗi tính năng mới đều có "lưới an toàn": nếu làm hỏng chất lượng xuất
  bản, bộ đánh giá đỏ ngay trong CI.
- Hạn chế chủ quan: 5/10 ca không có tài liệu trong dataset nên chỉ kiểm tra
  cấu trúc (không kiểm tra bám sát SGK) — sẽ bổ sung khi dataset có thêm sách
  thật; khi có khoá Gemini, chạy `python -m app.evaluate --provider gemini` để
  đánh giá trên mô hình thật.
