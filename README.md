# Soạn Giáo Án & Phiếu Bài Tập — AI Lesson Plan & Weekly Worksheet Generator

[![CI](https://github.com/DTKien2005/giao-an-generator/actions/workflows/ci.yml/badge.svg)](https://github.com/DTKien2005/giao-an-generator/actions/workflows/ci.yml)

Web app soạn **giáo án** và **phiếu bài tập tuần** bằng tiếng Việt, theo quy trình
*nháp → thẩm định → chỉnh sửa* (tối đa 3 vòng) và kết xuất `.docx` / `.pdf`.
Xem `PLANS.md` (thiết kế), `PLANS_V1-V5.md` (kế hoạch 5 phiên bản), `UPDATES.md`
(nhật ký đầy đủ), `REPORT.md` (tóm tắt cả dự án) và `reports/` (biên bản duyệt
từng phiên bản).

## Tính năng

- **Pipeline 3 vai trò:** tiếp nhận → truy xuất dataset → nháp → thẩm định →
  chỉnh sửa; dừng sớm khi không còn lỗi nghiêm trọng và điểm ≥ 8/10.
- **Đa nhà cung cấp:** Gemini, OpenAI, Anthropic (Claude), mô hình cục bộ
  (Ollama / LM Studio / vLLM) và **mock ngoại tuyến** — chọn trong tab Cài đặt,
  mô hình riêng cho từng vai trò, khoá API **mã hoá** trước khi lưu.
- **Lịch sử & phiên bản:** mọi kết quả lưu thành phiên bản mới; chỉnh sửa tiếp
  qua hộp chat (nhỏ → sửa một mục, lớn → chạy lại); xem diff màu giữa hai bản;
  **phục hồi** (rollback) về bất kỳ bản nào mà không mất lịch sử.
- **Giữ định dạng của bạn:** tải lên giáo án mẫu → app tự nhận cấu trúc mục và
  soạn theo đúng định dạng đó cho các lần sau.
- **OCR PDF quét** bằng Gemini Vision (không có khoá → bỏ qua trang an toàn).
- **Đăng nhập bật tiến bộ** + **sao lưu dữ liệu** một lệnh (giữ 10 bản).
- **Docker + CI** — pytest + bộ đánh giá chạy tự động trên mỗi push.

## Chạy thử nhanh (không cần API key)

```bash
pip install -r requirements.txt
python -m app.ingest                 # nạp dataset mẫu vào kho vector
python -m uvicorn app.main:app --port 8090
# mở http://127.0.0.1:8090 — chạy ở chế độ "mock" ngoại tuyến
```

## Dùng Gemini (hoặc OpenAI / Claude / Ollama)

Cách 1 — biến môi trường:

```bash
set GEMINI_API_KEY=...               # hoặc OPENAI_API_KEY / ANTHROPIC_API_KEY
python -m uvicorn app.main:app --port 8090
```

Cách 2 — tab **Cài đặt** trên web: chọn nhà cung cấp, mô hình riêng cho từng vai
trò (Writer / Reviewer / Reviser / Intake), dán khoá API. Máy cục bộ: chọn
"**Mô hình cục bộ**" và điền base URL (mặc định `http://localhost:11434/v1`).

## Dataset

```
dataset/
  grade_1/toan/{textbooks,lesson_plans,worksheets}/...
```

- Mỗi tệp có `*.meta.json` kèm theo (grade, subject, lesson, doc_type); nếu thiếu,
  script suy ra từ cấu trúc thư mục.
- Thêm tệp mới (kể cả PDF quét) xong chạy lại `python -m app.ingest`.

## CLI (không cần web)

```bash
python -m app.cli "Giáo án toán lớp 1 bài các số có hai chữ số" --type lesson_plan
```

## Bộ đánh giá chất lượng (v1)

10 ca đánh giá trong `eval/` (lớp 1–5, Toán / Tiếng Việt / Tiếng Anh) chấm bằng
rubric xác định — đủ mục theo định dạng, nội dung bám SGK, thời lượng hợp lý,
dấu tiếng Việt chuẩn, có kết xuất tệp:

```bash
python scripts/make_eval.py      # nếu chưa có eval/
python -m app.evaluate           # chạy với mock; thêm --provider gemini khi có khoá
```

## Kiểm thử

```bash
python -m pytest tests/ -q       # 48 test; CI chạy trên Python 3.12
```

## Đăng nhập (từ v3)

Mặc định app chạy **mở** (không đăng nhập) đúng như trước. Vào tab **Cài đặt →
Tài khoản** tạo tài khoản đầu tiên để bật đăng nhập: tài khoản đó **kế thừa toàn
bộ dữ liệu** đã tạo trong chế độ mở; sau đó mọi API yêu cầu đăng nhập, mỗi người
chỉ thấy hội thoại/tài liệu của mình. Người đã đăng nhập có thể tạo thêm người
dùng (tab Cài đặt → Tài khoản). Mật khẩu băm PBKDF2-SHA256 (240.000 vòng).

Quên mật khẩu (app cục bộ): dừng server rồi chạy
`python -c "from app import db; c=db.get_conn(); c.execute(\"DELETE FROM sessions\"); c.execute(\"DELETE FROM users\"); c.execute(\"INSERT INTO users (id,name,password_hash) VALUES (1,'shared','')\"); c.commit()"`
— app quay về chế độ mở, tạo lại tài khoản mới (dữ liệu cũ vẫn thuộc sentinel).

## Sao lưu dữ liệu (từ v3)

```bash
python -m app.backup     # tạo data/backups/backup_<thời_gian>.zip, giữ 10 bản gần nhất
```

Tệp zip chứa database (chụp nhất quán qua SQLite backup API), thư mục tài liệu
đã sinh, tệp tải lên và khoá mã hoá. Đặt lịch hằng ngày trên Windows (Task
Scheduler): chạy `python -m app.backup` trong thư mục dự án lúc 23:00.

```bat
schtasks /Create /SC DAILY /ST 23:00 /TN "GiaoAnBackup" /TR "cd /d H:\Web_Lam_Giao_An_Bang_Gemini && python -m app.backup"
```

## Cấu trúc dự án

```
app/            # mã nguồn (pipeline, providers, renderers, auth, backup, ocr, eval)
static/ templates/   # giao diện "vở học sinh" — không CDN, chạy offline
dataset/ eval/  # dữ liệu mẫu + 10 ca đánh giá
tests/          # 48 pytest (pipeline, API, render, auth, rollback…)
assets/fonts/   # font tiếng Việt nhúng (IBM Plex Serif, OFL) cho PDF
reports/        # biên bản duyệt code (≥3 vòng) + báo cáo (≥2 vòng) mỗi phiên bản
docs/DEPLOY.md  # triển khai: laptop, Cloudflare Tunnel, Docker, nâng cấp
```

## Triển khai & CI

Docker, truy cập từ xa qua Cloudflare Tunnel, lịch backup và nâng cấp: xem
**[docs/DEPLOY.md](docs/DEPLOY.md)**. Mỗi push vào `main` được CI (GitHub
Actions) chạy pytest + bộ đánh giá tự động (provider mock, không cần khoá).

## Biến môi trường

| Biến | Ý nghĩa | Mặc định |
|---|---|---|
| `GEMINI_API_KEY` | khoá Gemini (bỏ trống → dùng mock/embedding băm) | — |
| `DEFAULT_PROVIDER` | gemini / openai / anthropic / local / mock | tự theo khoá |
| `APP_DATA_DIR` | thư mục dữ liệu (SQLite, tệp sinh ra, khoá mã hoá) | `./data` |
| `APP_DATASET_DIR` | thư mục dataset | `./dataset` |
| `APP_RATE_LIMIT` | số lượt chạy / 10 phút / máy (giới hạn chi phí) | 10 |
| `APP_TRUST_PROXY` | `1` = tin `CF-Connecting-IP` từ loopback (đằng sau tunnel) | 0 |
| `APP_SETUP_TOKEN` | bắt buộc khi tạo tài khoản đầu tiên (chống chiếm quyền) | — |
| `APP_COOKIE_SECURE` | `1` = cookie phiên chỉ qua HTTPS (production) | 0 |
| `APP_BACKUP_COPY_DIR` | copy zip backup ra ngoài đĩa (thư mục riêng tư) | — |

Runbook go-live lên `https://giaoan.kinzz-server.io.vn` (Cloudflare Tunnel +
Access + Task Scheduler): xem [docs/DEPLOY.md](docs/DEPLOY.md).

## Bản quyền & nguồn

- Toàn bộ nội dung dataset/eval là **bài gốc tự soạn** — không kèm tài liệu có
  bản quyền (SGK thật chỉ nên nạp để dùng riêng, xem PLANS.md §10).
- Font PDF: [IBM Plex Serif](https://github.com/IBM/plex) — SIL OFL 1.1
  (`assets/fonts/LICENSE-IBMPlexSerif.txt`).
- Thư viện tham khảo `skills/` và `andrej-karpathy-skills-main/` chỉ dùng như
  tài liệu hướng dẫn, không nằm trong repo.
