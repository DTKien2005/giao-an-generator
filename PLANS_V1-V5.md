# PLANS_V1-V5.md — Kế hoạch 5 phiên bản tiếp theo (v1 → v5)

> Kế hoạch này được lập theo quy trình: **lập kế hoạch → duyệt → làm lại**, lặp lại
> **3 lần** trước khi chốt (nhật ký duyệt ở cuối tệp). Mỗi phiên bản sau khi hoàn
> thành được **review ≥ 3 vòng** (có lỗi thì sửa rồi duyệt lại), kèm **báo cáo
> `reports/vN_report.md`** được duyệt **≥ 2 vòng**, rồi mới commit + push lên
> GitHub (`DTKien2005/giao-an-generator`, nhánh `main`, tag `vN`).

## Nguyên tắc chung cho mọi phiên bản

- **Definition of Done:** code + test mới; toàn bộ pytest xanh; không làm hỏng
  chức năng đã có; cập nhật `README.md` + `UPDATES.md`; có `reports/vN_review.md`
  (≥ 3 vòng duyệt) và `reports/vN_report.md` (≥ 2 vòng duyệt); push kèm tag.
- **Không phá GitHub Actions:** mọi workflow có sẵn được giữ nguyên; workflow mới
  chỉ *thêm vào* và phải xanh ngay lần chạy đầu.
- **Chạy được ngoại tuyến:** mọi tính năng phải hoạt động với provider `mock`
  (không cần API key) để test/CI luôn chạy được.
- **Không commit bí mật:** thư mục `data/` (chứa khoá mã hoá, DB) đã nằm trong
  `.gitignore`; không bao giờ đưa token/khoá vào repo.

---

## v1 — Bộ đánh giá chất lượng (evaluation set) + requirements.txt

**Lý do:** PLANS.md §9-Phase 1 yêu cầu bộ đánh giá trên các bài thật — mục còn nợ
duy nhất của v0.x. Làm trước để bảo vệ chất lượng cho v2–v5.

**Việc cần làm**
1. `eval/` — 10 bài đánh giá gốc (tự soạn, không vi phạm bản quyền) cho lớp 1–5,
   các môn Toán / Tiếng Việt / Tiếng Anh: mỗi bài gồm `request.json` (grade,
   subject, lesson, doc_type) + `expected.json` (các mục bắt buộc theo format:
   mục tiêu, hoạt động, đáp án…).
2. `app/evaluate.py` — chạy pipeline (mock hoặc thật) trên 10 bài, chấm bằng
   rubric **xác định** (không dùng LLM chấm để CI ổn định):
   - đủ mục theo format spec; câu hỏi intake được hỏi đúng khi thiếu dữ liệu;
   - mục tiêu có *gốc* từ trích dẫn SGK (trùng từ khoá với chunk truy xuất);
   - phiếu bài tập phải có đáp án; giáo án phải có phụ lục;
   - tổng thời lượng hoạt động 30–45 phút; văn bản có dấu tiếng Việt chuẩn.
3. CLI: `python -m app.evaluate [--provider mock]` in bảng điểm từng bài.
4. `requirements.txt` (khóa phiên bản các thư viện đang dùng) + pytest cho eval
   (chấm điểm > ngưỡng trên provider mock).
5. Báo cáo kết quả chạy eval lần đầu vào `reports/v1_report.md`.

**Ngưỡng đạt:** 10/10 bài pass rubric với mock; pytest tổng (cũ + mới) xanh.

## v2 — OCR PDF quét bằng Gemini Vision (PLANS.md §3.1)

**Lý do:** mục còn nợ §3.1 — PDF quét (không có lớp chữ) hiện bị bỏ qua khi ingest.

**Việc cần làm**
1. `app/ocr.py` — với tệp PDF không có lớp chữ (PyMuPDF `page.get_text()` rỗng):
   nếu có khoá Gemini → dựng ảnh từng trang (dpi 150) → gọi `gemini-2.5-flash`
   kèm ảnh (inlineData base64) yêu cầu transcribe tiếng Việt giữ cấu trúc dòng;
   không có khoá → bỏ qua trang và ghi cảnh báo vào kết quả ingest.
2. Ghép vào `app/ingest.py`: `file_to_text` PDF thử lớp chữ trước, rớt xuống OCR.
3. Test: PDF có lớp chữ đi thẳng (không gọi OCR); PDF "quét" (tạo bằng cách vẽ
   chữ thành ảnh) không có khoá → bị bỏ qua an toàn; hàm dựng ảnh + gọi API được
   test bằng monkeypatch (không gọi mạng thật).
4. Mức xác nhận sống: khi có khoá thật, chạy 1 PDF quét mẫu — ghi nhận thủ công
   vào báo cáo (CI không bắt buộc).

**Ngưỡng đạt:** ingest không bao giờ lỗi vì PDF quét; pytest xanh; logic chọn đường
đồng được test đầy đủ.

## v3 — Đăng nhập nhiều người dùng + sao lưu (PLANS.md §9-Phase 6, phần còn nợ)

**Việc cần làm**
1. Auth **bật tiến bộ**: chưa có user nào → app chạy như hiện tại (không đăng
   nhập) để không phá người dùng hiện hữu; tạo user đầu tiên qua `POST /api/setup`
   (tên + mật khẩu, PBKDF2-SHA256, 240k vòng) thì mọi API (trừ `/`, `/api/setup`,
   `/api/login`, static) yêu cầu cookie phiên.
2. Phiên: token ngẫu nhiên (secrets) lưu bảng `sessions`, cookie HttpOnly, hạn
   7 ngày; `POST /api/login`, `POST /api/logout`, `GET /api/me`. UI: trang/gợi ý
   đăng nhập khi nhận 401.
3. Mỗi user thấy conversation/document của riêng mình (truy vấn đã có `user_id`,
   thêm điều kiện lọc).
4. `python -m app.backup` — nén `data/` (app.db + generated + uploads) thành
   `backups/backup_<timestamp>.zip`, giữ 10 bản gần nhất; hướng dẫn đặt lịch
   Windows Task Scheduler trong README.
5. Test: setup → login → truy cập được; sai mật khẩu 401; user A không thấy
   conversation của user B; backup tạo được tệp zip chứa app.db; toàn bộ test cũ
   xanh (chế độ chưa bật auth).

**Ngưỡng đạt:** pytest xanh cả hai chế độ (chưa bật / đã bật auth).

## v4 — Phục hồi phiên bản (rollback) + quản lý hội thoại

**Việc cần làm**
1. `POST /api/versions/{id}/restore` — **phiên kiểu không phá vỡ**: nội dung phiên
   bản cũ được lưu thành phiên bản mới (v+1, ghi rõ "phục hồi từ vX") — giữ nguyên
   chuỗi audit/diff (đúng tinh thần plan §5 "roll back" mà không mất lịch sử).
   Render lại docx/pdf cho phiên mới.
2. Nút "Phục hồi phiên bản này" trong UI (trình chọn phiên bản), dùng SSE tiến độ
   như các luồng khác.
3. `DELETE /api/conversations/{id}` — xoá mềm (đánh dấu `deleted_at`), ẩn khỏi
   Lịch sử; xác nhận bằng hộp thoại trong UI.
4. Test: restore tạo v+1 với nội dung giống hệt phiên cũ + ghi chú đúng; sau
   restore có thể diff v_new với v_old (không khác biệt); xoá hội thoại ẩn danh
   sách nhưng dữ liệu vẫn còn (truy vấn trực tiếp).

**Ngưỡng đạt:** pytest xanh; luồng restore chạy được trong UI.

## v5 — Triển khai: Docker, CI GitHub Actions, tài liệu chạy thật

**Việc cần làm**
1. `Dockerfile` (python:3.12-slim, non-root, `pip install -r requirements.txt`,
   CMD uvicorn 0.0.0.0:8090) + `.dockerignore`.
2. `.github/workflows/ci.yml` — *tệp mới hoàn toàn* (repo mới, không đụng workflow
   nào có sẵn): checkout → Python 3.12 → pip install → `pytest -q` (mock, không
   cần khoá). Phải xanh ngay lần đầu push.
3. Kiểm tra Docker build chạy được cục bộ nếu có Docker; nếu máy không có Docker
   thì ghi rõ trong báo cáo (build chỉ được xác nhận qua CI hoặc hướng dẫn).
4. `docs/DEPLOY.md` — chạy trên laptop + Cloudflare Tunnel (plan §8), đặt biến
   môi trường, đặt lịch backup, nâng cấp (git pull → pip install → restart).
5. Test: không thêm test chức năng mới; bảo đảm toàn bộ pytest xanh trong môi
   trường CI (Python 3.12) — nếu lệnh phụ thuộc chỉ chạy được 3.14 thì ghi nhận
   và điều chỉnh requirements cho tới khi CI xanh.

**Ngưỡng đạt:** CI xanh trên GitHub; Dockerfile/DEPLOY.md hoàn chỉnh; pytest xanh.

---

## Nhật ký duyệt kế hoạch (3 vòng: duyệt → làm lại)

### Vòng 1
Phát hiện khi duyệt bản nháp đầu:
1. Thiếu `requirements.txt` ở baseline → môi trường không tái lập được; chuyển
   sang **v1** (cần trước cả CI ở v5).
2. Rubric đánh giá v1 lúc đầu định dùng LLM chấm → không ổn định trong CI; đổi
   sang **rubric xác định** (kiểm tra cấu trúc/gốc kiến thức bằng code).
3. v3 auth nếu bắt buộc ngay sẽ **phá toàn bộ test cũ** và người dùng hiện hữu;
   đổi sang thiết kế "bật tiến bộ" (auth chỉ kích hoạt khi có user đầu tiên).
4. Thiếu tiêu chí hoàn thành rõ ràng mỗi phiên → thêm mục *Ngưỡng đạt* và
   *Definition of Done* chung.

### Vòng 2
Phát hiện khi duyệt bản nháp thứ hai:
1. v2 cần làm rõ **điều kiện nghiệm thu trung thực**: OCR thật chỉ kiểm chứng
   được khi có khoá Gemini — CI chỉ test logic chọn đường (có/không lớp chữ, có/
   không khoá) bằng monkeypatch; ghi rõ trong kế hoạch để không "đánh lừa" CI.
2. v4 rollback có 2 ngữ nghĩa (trỏ lại phiên bản cũ hay tạo bản mới) → chốt
   **tạo bản mới từ nội dung cũ** để lịch sử/diff không đứt.
3. v3 backup nên là **CLI + đặt lịch** thay vì endpoint web (đơn giản, an toàn,
   không lộ đường tấn công); giữ 10 bản gần nhất chống đầy đĩa.
4. v5 CI phải chọn phiên bản Python ổn định (3.12) và khai báo rõ khác biệt với
   môi trường lập trình (3.14); nếu có lệch phụ thuộc thì sửa requirements.

### Vòng 3 (chốt)
Kiểm tra cuối:
1. Mỗi phiên bản đúng chuẩn "một phần việc vừa sức": ~1 module chính + test +
   tài liệu — không dồn việc lớn vào một phiên.
2. Thống nhất quy trình push: **1 commit cho mỗi phiên bản** (code + test +
   report + UPDATES.md) + tag `vN`; không bao giờ sửa lịch sử đã push.
3. Rà an toàn: không bí mật trong repo; `data/` đã ignore; workflow mới chỉ thêm
   không đụng cái cũ; mọi tính năng chạy được với mock.
4. Kết luận: kế hoạch đạt — chốt nội dung như trên.
