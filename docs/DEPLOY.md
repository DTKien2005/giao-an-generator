# Triển khai go-live (v6) — `https://giaoan.kinzz-server.io.vn`

> Kế hoạch đầy đủ: `PLANS_V6.md`. Tài liệu này là runbook từng bước — làm đúng
> thứ tự, nhất là **bật Access trước khi coi hostname là "đã phát hành"**.

## Kiến trúc

```
Điện thoại / thiết bị khác
   │  HTTPS
   ▼
Cloudflare edge ── Access (chỉ email của chủ; mã một lần qua email)
   │  tunnel (chỉ outbound; không mở port trên laptop)
   ▼
cloudflared (dịch vụ Windows) ──► http://127.0.0.1:8090
   ▼
uvicorn app.main:app  (bind 127.0.0.1)
   ├─ SQLite + tệp sinh ra + khoá mã hoá trong ./data
   └─ Gemini API (khoá lưu mã hoá, hoặc GEMINI_API_KEY)
```

Hai lớp bảo vệ độc lập: **Cloudflare Access** chặn người lạ ở biên; **đăng nhập
của app** phân tách người dùng/dữ liệu bên trong.

## Phase 0 — Chạy thật trên laptop (vẫn riêng tư)

```powershell
cd H:\Web_Lam_Giao_An_Bang_Gemini
git pull
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest tests/ -q            # phải 61/61 xanh
python -m app.ingest
python -m uvicorn app.main:app --host 127.0.0.1 --port 8090
```

1. Mở `http://127.0.0.1:8090`, dán khoá Gemini ở Cài đặt, chạy **một giáo án
   thật** trọn vẹn 3 vòng thẩm định (SSE không đứng, không 524).
2. **Tạo tài khoản đầu tiên NGAY BÂY GIỜ** (Cài đặt → Tài khoản) — trước khi
   có bất kỳ sự phơi nhiễm nào. Tài khoản này kế thừa toàn bộ dữ liệu hiện có.
   Tuỳ chọn chặt hơn: đặt `APP_SETUP_TOKEN` (biến môi trường) — khi có, tạo
   tài khoản đầu tiên bắt buộc phải nhập token này (so sánh constant-time).

## Phase 1 — Tên miền và tunnel (chưa phát hành hostname)

1. Cloudflare → Overview = **Active** (nếu Pending: *Check nameservers now*).
2. DNS → Records: xoá A/AAAA cũ của root và `www` (MX giữ lại nếu có dùng mail).
3. Zero Trust → Networks → Tunnels → Create → Cloudflared → Windows; chạy lệnh
   cài trong PowerShell **Administrator** (cài dịch vụ; token nằm trong lệnh —
   không đưa token vào repo).
4. Public Hostname: `giaoan` + `kinzz-server.io.vn` → `HTTP` →
   **`127.0.0.1:8090`** (dùng `127.0.0.1`, KHÔNG dùng `localhost` — localhost có
   thể phân giải sang IPv6 trong khi uvicorn chỉ bind IPv4).

## Phase 2 — Khoá cửa trước (làm NGAY sau bước 4, trước khi thử từ điện thoại)

Zero Trust → Access → Applications → Self-hosted → hostname
`giaoan.kinzz-server.io.vn`, policy: allow chỉ email của chủ (Free plan đủ 50
người). **Hostname chưa có Access policy coi như chưa phát hành** — đừng gửi
link cho ai cho tới khi bước này xong và kiểm thử "người lạ bị chặn" đạt.

## Phase 3 — Sống sót qua reboot

1. Sửa `scripts\windows\web_env.bat` (tự tạo từ mẫu, git-ignored):
   `APP_SETUP_TOKEN=...`, `APP_BACKUP_COPY_DIR=D:\du-phong\giao-an`, khoá nếu muốn.
2. Chạy `scripts\windows\install_tasks.bat` — tạo 2 task: `GiaoAnWeb`
   (logon + 1 phút), `GiaoAnBackup` (23:00 hằng ngày). Gỡ: `uninstall_tasks.bat`.
3. Nguồn điện: sleep = Never khi cắm điện; tắt hibernate.
4. Lưu ý: task chạy lúc **logon** — laptop pilot chấp nhận "sau khi đăng nhập
   Windows" (muốn trước-logon thì cần dịch vụ Windows/VPS — ngoài phạm vi).

## Phase 4 — Sao lưu

1. `APP_BACKUP_COPY_DIR` trỏ vào thư mục **riêng tư** (Drive/OneDrive riêng hoặc
   USB) — zip chứa **khoá mã hoá API**, không để chỗ công khai, không share link.
2. Chạy thử `python -m app.backup`: zip hợp lệ + bản copy khớp kích thước.
3. **Diễn tập khôi phục**: dừng app → giải nén zip vào `APP_DATA_DIR` mới →
   khởi động → hội thoại/phiên bản hiện lại **và** tải được 1 file .docx, khoá
   API đã lưu vẫn giải mã được.

## Phase 5 — Checklist nghiệm thu

Xem §6 của `PLANS_V6.md` (gồm cả các mục mobile web 390×844 / 360×800 / 768×1024).

## Di chuyển lên VPS / mini PC (khi cần uptime)

1. `python -m app.backup` trên laptop → copy zip sang máy mới.
2. Trên máy mới: clone repo → venv → giải nén zip vào `data/` → chạy app.
3. Cài lại cloudflared với **cùng tunnel token** — DNS không đổi.

## Nâng cấp

```powershell
git pull
.venv\Scripts\pip install -r requirements.txt
python -m app.backup        # sao lưu trước khi nâng cấp
python -m app.ingest        # nếu dataset có tệp mới
# restart: kết thúc uvicorn (task GiaoAnWeb sẽ tự chạy lại lúc logon tiếp theo,
# hoặc chạy lại run_web.bat)
```

Schema tự migrate khi khởi động; các run dở dang sau crash được đánh dấu lỗi.

## Biến môi trường production (`web_env.bat` hoặc hệ thống)

| Biến | Ý nghĩa |
|---|---|
| `APP_TRUST_PROXY=1` | tin `CF-Connecting-IP` từ loopback (rate limit per IP thật) |
| `APP_COOKIE_SECURE=1` | cookie phiên chỉ gửi qua HTTPS |
| `APP_SETUP_TOKEN=...` | bắt buộc khi tạo tài khoản đầu tiên (chống chiếm quyền) |
| `APP_BACKUP_COPY_DIR=D:\...` | copy zip backup ra ngoài đĩa (thư mục riêng tư) |
| `GEMINI_API_KEY=...` | (tuỳ chọn) nếu không dán khoá qua Cài đặt |
