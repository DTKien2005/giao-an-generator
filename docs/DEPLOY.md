# Hướng dẫn triển khai (v5)

## 1. Chạy trên laptop (đơn giản nhất)

```bash
pip install -r requirements.txt
python -m app.ingest
python -m uvicorn app.main:app --port 8090
# mở http://127.0.0.1:8090
```

Đặt khoá Gemini trong tab **Cài đặt** (mã hoá trước khi lưu) hoặc qua biến môi
trường `GEMINI_API_KEY`.

## 2. Truy cập từ xa qua Cloudflare Tunnel (plan §8)

Không mở cổng router. Cài [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
rồi:

```bash
cloudflared tunnel --url http://127.0.0.1:8090
```

Muốn gắn tên miền riêng: `cloudflared tunnel create giao-an` → cấu hình DNS
`CNAME giaoan.example.com → giao-an.cfargotunnel.com` → chạy
`cloudflared tunnel run giao-an`. **Khi mở ra ngoài, bật đăng nhập** (tab Cài
đặt → Tài khoản) — xem README mục "Đăng nhập".

## 3. Chạy bằng Docker

```bash
docker build -t giao-an .
docker run -d --name giao-an -p 8090:8090 \
  -v C:\path\to\data:/srv/data \
  -e GEMINI_API_KEY=... \
  giao-an
```

- Gắn volume `/srv/data` để giữ DB, tài liệu đã sinh và khoá mã hoá giữa các lần
  chạy (Windows: đường dẫn tuyệt đối; Linux/Mac: `/opt/giao-an/data:/srv/data`).
- Ảnh chạy bằng user không đặc quyền, có HEALTHCHECK.

## 4. Sao lưu định kỳ

```bash
python -m app.backup        # zip vào data/backups/, giữ 10 bản
```

Đặt lịch Windows (Task Scheduler) — lệnh `schtasks` có sẵn trong README. Trên
Linux/Mac: crontab `0 23 * * * cd /srv/app && python -m app.backup`.

## 5. Nâng cấp phiên bản

```bash
git pull
pip install -r requirements.txt     # hoặc docker build -t giao-an .
python -m app.ingest                # nạp lại dataset nếu có tệp mới
# restart uvicorn / docker restart giao-an
```

Schema database tự migrate khi khởi động (cột mới được thêm bằng ALTER TABLE,
dữ liệu cũ giữ nguyên). Sao lưu trước khi nâng cấp: `python -m app.backup`.

## 6. CI trên GitHub

`.github/workflows/ci.yml` chạy pytest + bộ đánh giá (provider mock, không cần
khoá) với Python 3.12 mỗi khi push/PR vào `main`.
