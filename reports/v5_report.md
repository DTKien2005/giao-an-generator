# REPORT v5 — Docker, CI GitHub Actions, tài liệu triển khai
**Ngày:** 2026-10-26 · **Kế hoạch:** `PLANS_V1-V5.md` mục v5 · **Duyệt code:** `reports/v5_review.md` (3 vòng)

## Tóm tắt
Đóng gói và tự động hoá: Dockerfile (python:3.12-slim, non-root, volume dữ
liệu, healthcheck), workflow CI chạy pytest + bộ đánh giá tự động trên mỗi push/PR,
và tài liệu triển khai đầy đủ từ laptop tới Cloudflare Tunnel. CI còn bắt được
một lỗi thật: font PDF chỉ khai báo đường dẫn Windows — đã sửa bằng cách vendored
font có dấu tiếng Việt vào repo.

## Những gì đã làm
1. **`Dockerfile`** — python:3.12-slim, user không đặc quyền `appuser`, volume
   `/srv/data` (DB + tệp sinh ra + khoá mã hoá), `HEALTHCHECK` gọi `/api/me`,
   `.dockerignore` loại data/tests/thư viện tham khảo.
2. **`.github/workflows/ci.yml`** — *file mới hoàn toàn* (repo mới, không đụng
   action có sẵn nào của người dùng): Python 3.12 → `pip install -r
   requirements.txt` → `pytest -q` → chạy bộ đánh giá `app.evaluate` (provider
   mock, **không cần khoá API** trong CI).
3. **`docs/DEPLOY.md`** — chạy laptop, Cloudflare Tunnel (kèm cảnh báo bật đăng
   nhập khi mở ra ngoài), Docker run với volume, lịch backup `schtasks`/cron,
   quy trình nâng cấp (schema tự migrate khi khởi động).
4. **Fix từ CI (quan trọng nhất):** vendored IBM Plex Serif (OFL) vào
   `assets/fonts/` làm font PDF chính — rendering nhất quán Windows/Linux/Docker;
   đăng ký family đậm `VNFont-Bold`; font Windows chỉ còn fallback.
5. README trỏ tới DEPLOY.md và mô tả CI.

## Kết quả kiểm chứng
- **CI GitHub: xanh (success)** trên commit của v5 — https://github.com/DTKien2005/giao-an-generator/actions
- pytest **48/48 trên cả Python 3.14 (máy phát triển) và 3.12 (môi trường CI)**
- Bộ đánh giá: **10/10 PASS**
- 5 tag v1–v5 trên remote, đúng commit

## Ý nghĩa & hạn chế
- Từ đây mọi thay đổi đều được kiểm tự động trước khi thành "hỏng main"; ai
  clone về cũng build được vì font đã nằm trong repo (không phụ thuộc font hệ).
- Hạn chế trung thực: Docker **build** chưa chạy được trên máy này (daemon
  không khởi động) — Dockerfile được soát chuẩn và CI chạy cùng base image
  python:3.12; người dùng chạy `docker build` theo DEPLOY.md là đủ. OCR thật
  (v2) tương tự: đường gọi Gemini Vision được kiểm bằng test hình dạng request.
