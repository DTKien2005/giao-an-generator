# REPORT v6 — Go-live: triển khai an toàn lên `giaoan.kinzz-server.io.vn`

**Ngày:** 2026-10-26 · **Kế hoạch:** `PLANS_V6.md` (5 vòng duyệt kế hoạch; vòng 1
là review của Codex với 25 findings) · **Duyệt code:** `reports/v6_review.md`
(5 vòng; Codex reviewer 2 lượt quét — 25 + 15 findings)
**Phong cách:** báo cáo theo cấu trúc *evidence-traceable* — mỗi tuyên bố kèm
bằng chứng (lệnh/test/screenshot logic) và giới hạn của bằng chứng đó.

---

## 1. Abstract (tóm tắt)

Version v6 chuyển app từ "chạy cục bộ" sang **go-live**: hosting trên laptop,
phát hành qua Cloudflare Tunnel + Access, tự khởi động sau reboot, backup
ngoài đĩa, kèm một đợt vá bảo mật do review tự động (Codex) phát hiện. Kết quả
đo được: **65/65** test pytest (tăng từ 48), **10/10** ca đánh giá, **40 findings**
từ Codex được xử lý/ghi nhận (25 plan-level + 15 code-level), **2 bug cũ**
(bảngLogin overlay luôn hiện từ v3; run/SSE không kiểm quyền từ v3) được phát
hiện và đóng. Các bước cấu hình Cloudflare là thao tác tay của chủ tài khoản —
runbook và checklist nghiệm thu đã sẵn trong `docs/DEPLOY.md` / `PLANS_V6.md` §6.

## 2. Phương pháp

1. **Kế hoạch:** `PLANS_V6.md` soạn sẵn → Codex duyệt toàn văn + quét code cũ
   (lượt 1) → 5 vòng duyệt (Codex + self theo `security-audit`) → đóng băng.
2. **Triển khai:** WP0→WP1→WP2→WP4→WP3→WP6→WP5; sau mỗi gói: pytest + cập nhật
   `REPORT.md` (compact).
3. **Duyệt triển khai:** 5 vòng như trên; Codex quét bug lần 2 trên code cuối.
4. **Minh chứng tự động:** pytest, `python -m app.evaluate`, `node --check`,
   trình duyệt thật (IAB) với `setViewportSize` và đo DOM (`scrollWidth`,
   `getComputedStyle`).

## 3. Kết quả và bằng chứng

| # | Tuyên bố | Bằng chứng |
|---|---|---|
| 3.1 | Run/SSE chỉ chủ sở hữu đọc được | `tests/test_v6.py::test_run_endpoints_check_ownership` (404 chéo-user; 200 chủ sở hữu); cột mới `runs.user_id` + migration backfill (`app/db.py::_migrate`) |
| 3.2 | Upload không thể path-traversal, giới hạn 20 MB | `test_upload_rejects_traversal_and_oversize` (413 với tệp quá hạn; 400 với `../`) |
| 3.3 | Tài khoản đầu tiên không thể bị chiếm | `APP_SETUP_TOKEN` (compare_digest bytes) + atomic claim `UPDATE … WHERE password_hash=''` — `test_setup_token_required`, `test_setup_claim_is_atomic`, `test_setup_fast_reject_when_claimed` |
| 3.4 | Rate limit vẫn đúng per-IP sau tunnel | `client_ip()` chỉ tin `CF-Connecting-IP` từ loopback, validate `ipaddress`, bucket có trần 10 000 — `test_client_ip_trust_rules` (7 nhánh), `test_rate_limit_buckets_separate_by_forwarded_ip`, `test_rate_limit_buckets_bounded` |
| 3.5 | Backup nguyên vẹn cả khi copy fail | atomic `.part`→`os.replace` + integrity check; copy dir trong `data/` bị từ chối; CLI exit non-zero — `test_backup_atomic_and_off_disk_copy`, `test_backup_copy_dir_rules` |
| 3.6 | Site sống sót sau crash | startup reconciliation đánh dấu run dở thành error (`app/main.py::lifespan`); `/healthz` liveness không auth — `test_healthz_open_and_when_auth_enabled` |
| 3.7 | Mobile web (không native app) | 390×844 / 360×800 / 768×1024: `scrollWidth == clientWidth`, 0 element tràn, input 16 px, button 44 px — đo bằng DOM qua IAB; chạy trọn lượt soạn ở viewport 390 thành công; SSE heartbeat 15 s + auto-reconnect (cap 20) |
| 3.8 | Chất lượng pipeline không tụt | `python -m app.evaluate` → 10/10 sau mỗi gói triển khai |

## 4. Phát hiện quan trọng (mới + cũ)

1. **[SEC, cũ — v3] Run/SSE không kiểm quyền** (Codex R1-1): mọi user đăng nhập
   đọc được run của người khác theo id tuần tự. Đã đóng (3.1).
2. **[BUG, cũ — v3] Login overlay luôn hiển thị** ở chế độ mở: CSS
   `display:flex` đè `hidden`. Phát hiện tình cờ qua screenshot khi xác minh
   mobile; đóng bằng `.login-overlay[hidden]{display:none}`.
3. **[SEC, mới] `/api/setup` tốn 240k-iteration hash mỗi request** khi đã có
   tài khoản → CPU exhaustion. Đóng bằng fast-reject 409 + throttle.
4. **[BUG, mới] Patch "im lặng"**: script vá với `\n` escape sai không áp dụng
   heartbeat 15 s mà không báo lỗi — chỉ phát hiện nhờ Codex quét lại (R2-6).
   Quy trình sửa: mọi patch sau đó được xác minh bằng grep/AST.
5. **[BUG, mới] Race `_finish`** — subscriber gắn giữa "publish" và "set done"
   treo SSE vĩnh viễn. Đóng bằng cách set state trước publish.

## 5. Hạn chế của bằng chứng (đọc kỹ trước khi tin)

- Các kiểm tra là **cục bộ + mock provider**; lượt gọi Gemini thật chỉ khi chủ
  nhà dán khoá (checklist §6 mới chốt được 524/SSE trên domain thật).
- **Docker build chưa chạy được trên máy này** (daemon không khởi động);
  Dockerfile được soát + CI dùng cùng base image.
- OCR thật, di chuyển VPS, và toàn bộ Phase 1–5 go-live là **việc tay của chủ
  tài khoản Cloudflare** — app side đã sẵn sàng, còn lại là runbook.
- R2-2 (race version khi edit/restore đồng thời) chấp nhận có ghi nhận: UI đã
  khoá nút; đa người dùng đồng thời nằm ngoài phạm vi pilot.

## 6. Kết luận

Mọi mã nguồn của v6 đã được triển khai, kiểm thử tự động (65/65, 10/10), duyệt
5 vòng với Codex làm reviewer độc lập, và tài liệu go-live hoàn chỉnh. Việc
còn lại thuộc về chủ sở hữu hệ thống: chạy runbook `docs/DEPLOY.md` trên tài
khoản Cloudflare và tick checklist `PLANS_V6.md` §6; kết quả cần được ghi
thêm vào báo cáo này ở mục 7 khi hoàn tất.

## 7. Phụ lục: kết quả go-live thực tế (chờ chủ nhà điền)

- [ ] Zone Active, DNS cũ dọn xong — ngày: ____
- [ ] Truy cập từ điện thoại qua Access — ngày: ____
- [ ] Checklist `PLANS_V6.md` §6 tick đủ — ngày: ____
