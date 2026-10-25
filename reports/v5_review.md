# REVIEW v5 — Docker, CI GitHub Actions, tài liệu triển khai
**Ngày:** 2026-10-26 · **Phạm vi:** `Dockerfile`, `.dockerignore`, `.github/workflows/ci.yml`, `docs/DEPLOY.md`, `assets/fonts/` (fix từ review), `README.md`

---

## Vòng 1 — sau khi triển khai xong
**Kiểm chứng:** YAML workflow parse được (PyYAML: 1 job `tests`); pytest 48/48
trên Python 3.14. **Docker build thất bại — daemon không khởi động được trên máy
này** (Docker Desktop cài nhưng engine không lên). Quyết định trung thực theo
kế hoạch: không giả vờ build OK — đẩy CI lên GitHub để xác nhận môi trường 3.12
thay thế.

**Phát hiện (lỗi thật — CI bắt được ngay lần chạy đầu):**
1. **CI đỏ:** 3 test fail trên Linux (`test_api` download PDF 404,
   `test_full_evaluation_passes_with_mock` 0/10, `test_format_preserve`
   "page 0 not in document"). Nguyên nhân gốc: `render_pdf` chỉ tìm font hệ
   điều hành Windows (`C:\Windows\Fonts\times.ttf`) — không tồn tại trên Ubuntu
   runner → mọi render PDF lỗi, phiên bản chỉ lưu được docx.

## Vòng 2 — sau khi sửa (fix font)
**Bản sửa:** vendored **IBM Plex Serif** (OFL 1.1, đã kiểm tra phủ đủ glyph
tiếng Việt: ế ộ ị ữ ơ ư Đ bằng `has_glyph`) vào `assets/fonts/` kèm LICENSE;
`render_pdf` dùng font vendored làm chính (kèm mapping đậm `VNFont-Bold`),
font Windows chỉ còn là fallback. 

**Kiểm chứng:** pytest **48/48 trên Python 3.14** và **48/48 trên Python 3.12**
(venv 3.12.10 + requirements khóa — đúng môi trường CI); eval **10/10**; PDF với
font mới trích xuất đúng dấu; push lại → **CI GitHub xanh (completed: success)**.
Tag `v5` được chuyển sang commit xanh (tag vừa push phút trước, chưa ai dùng).

**Xác nhận Docker:** daemon vẫn không chạy được cục bộ — Dockerfile được soát
chỉ tiêu chuẩn (slim base, non-root, volume `/srv/data`, HEALTHCHECK) và build
thật sẽ do người dùng/CI thực hiện; ghi rõ hạn chế này trong báo cáo, không
tuyên bố đã build.

## Vòng 3 — duyệt chốt
**Kiểm chứng cuối:**
1. CI xanh trên commit đầu v5-fix; 5 tag v1–v5 đều trên remote.
2. `ci.yml` chỉ **thêm file mới**, không đụng workflow nào có sẵn (repo mới
   không có workflow cũ → không phá action nào của người dùng).
3. `.dockerignore` loại `data*/`, `tests/`, thư viện skills — không đưa bí mật
   hay rác vào image; `.gitignore` che `.venv*/` (venv 3.12 cục bộ).
4. `docs/DEPLOY.md` rà lại: đủ laptop/Tunnel/Docker/backup/nâng cấp/CI; lệnh
   backup tham chiếu đúng README.

**Kết luận:** không còn lỗi. Chốt v5.
