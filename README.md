# Soạn Giáo Án & Phiếu Bài Tập — AI Lesson Plan & Weekly Worksheet Generator

Web app soạn **giáo án** và **phiếu bài tập tuần** bằng tiếng Việt, theo quy trình
*nháp → thẩm định → chỉnh sửa* (tối đa 3 vòng) và kết xuất `.docx` / `.pdf`.
Xem `PLANS.md` (thiết kế) và `UPDATES.md` (nhật ký phiên bản).

## Chạy thử nhanh (không cần API key)

```bash
pip install fastapi uvicorn python-multipart httpx jinja2 python-docx reportlab pymupdf cryptography numpy
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

Cách 2 — tab **Cài đặt** trên web: chọn nhà cung cấp, mô hình riêng cho từng vai trò
(Writer / Reviewer / Reviser / Intake), dán khoá API (được **mã hoá** trước khi lưu).
Máy cục bộ (Ollama / LM Studio / vLLM): chọn "Mô hình cục bộ" và điền base URL
(mặc định `http://localhost:11434/v1`).

## Dataset

```
dataset/
  grade_1/toan/{textbooks,lesson_plans,worksheets}/...
```

- Mỗi tệp có `*.meta.json` kèm theo (grade, subject, lesson, doc_type); nếu thiếu,
  script suy ra từ cấu trúc thư mục.
- Thêm tệp mới xong chạy lại `python -m app.ingest`.

## CLI (không cần web)

```bash
python -m app.cli "Giáo án toán lớp 1 bài các số có hai chữ số" --type lesson_plan
```

## Kiểm thử

```bash
python -m pytest tests/ -q
```

## Bộ đánh giá chất lượng (v1)

10 ca đánh giá trong `eval/` (lớp 1–5, Toán / Tiếng Việt / Tiếng Anh) chấm bằng
rubric xác định — đủ mục theo định dạng, nội dung bám SGK, thời lượng hợp lý,
dấu tiếng Việt chuẩn, có kết xuất tệp:

```bash
python scripts/make_eval.py      # nếu chưa có eval/
python -m app.evaluate           # chạy với mock; thêm --provider gemini khi có khoá
```

## Cài đặt

```bash
pip install -r requirements.txt
```

## Đăng nhập (từ v3)

Mặc định app chạy **mở** (không đăng nhập) đúng như trước. Vào tab **Cài đặt →
Tài khoản** tạo tài khoản đầu tiên để bật đăng nhập: tài khoản đó **kế thừa toàn
bộ dữ liệu** đã tạo trong chế độ mở; sau đó mọi API yêu cầu đăng nhập, mỗi người
chỉ thấy hội thoại/tài liệu của mình. Người đã đăng nhập có thể tạo thêm người
dùng (tab Cài đặt → Tài khoản). Mật khẩu băm PBKDF2-SHA256 (240.000 vòng).

Quên mật khẩu (app cục bộ): dừng server rồi chạy
`python -c "from app import db,auth; c=db.get_conn(); c.execute(\"DELETE FROM sessions\"); c.execute(\"DELETE FROM users\"); c.execute(\"INSERT INTO users (id,name,password_hash) VALUES (1,'shared','')\"); c.commit()"`
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

## Biến môi trường

| Biến | Ý nghĩa | Mặc định |
|---|---|---|
| `GEMINI_API_KEY` | khoá Gemini (bỏ trống → dùng mock/embedding băm) | — |
| `DEFAULT_PROVIDER` | gemini / openai / anthropic / local / mock | tự theo khoá |
| `APP_DATA_DIR` | thư mục dữ liệu (SQLite, tệp sinh ra, khoá mã hoá) | `./data` |
| `APP_DATASET_DIR` | thư mục dataset | `./dataset` |
| `APP_RATE_LIMIT` | số lượt chạy / 10 phút / máy (giới hạn chi phí) | 10 |
