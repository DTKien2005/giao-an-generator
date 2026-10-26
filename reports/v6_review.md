# REVIEW v6 — Go-live (WP0–WP6): 5 vòng duyệt triển khai
**Ngày:** 2026-10-26 · **Kế hoạch:** `PLANS_V6.md` (đóng băng sau 5 vòng duyệt kế hoạch) · **Reviewer:** Codex (`codex exec` 0.164.0, read-only) + self-review theo skill `security-audit` (guidance mode)

> Mỗi vòng = chạy kiểm chứng + soi code (self) hoặc Codex quét; có lỗi thì sửa và
> vòng sau kiểm lại phần sửa. Kèm theo mỗi gói triển khai, `REPORT.md` được
> compact lại (mục §0).

---

## Vòng 1 — sau WP0 (security/bug fixes) + WP1 (client IP)
**Kiểm chứng:** pytest toàn bộ; `test_run_endpoints_check_ownership` chứng minh
người dùng khác nhận 404 trên `/api/runs/{id}` và SSE; `test_client_ip_trust_rules`
7 nhánh tin/cấm; suite **65 test** (tăng từ 48).

**Phát hiện (đã sửa):**
1. Test `/api/me` cũ so sánh trọn dict → fail khi thêm `setup_token_required`
   (thay đổi hợp lệ, test phải cập nhật).
2. Patch hàng loạt bằng script heredoc có `\n` escape sai → khối `stream()`
   (heartbeat 15 s + finally gỡ subscriber) **không được áp dụng** mà không báo
   lỗi — chính Codex bắt lại ở vòng 4 (R2-6). Bài học: mọi patch phải kiểm
   chứng bằng grep/AST sau khi chạy.
3. `hmac.compare_digest` từ chối str non-ASCII → so sánh dạng bytes.

## Vòng 2 — sau WP2 (setup token/atomic claim) + WP4 (backup)
**Kiểm chứng:** `test_setup_token_required` (403/403/200 + boolean exposure),
`test_setup_claim_is_atomic`, `test_backup_atomic_and_off_disk_copy`,
`test_backup_copy_dir_rules` (dest trong `data/` bị từ chối, copy fail không
đụng zip gốc), pytest **61/61** thời điểm đó.

**Phát hiện (đã sửa):**
1. Test cũ dùng mật khẩu 7 ký tự → bị chính sách mới chặn (đúng thiết kế) →
   test fail giữa chừng → **reset cuối test không chạy** → auth dính lại cho
   cả suite (hiện tượng "20 failed"). Sửa: mật khẩu hợp lệ + **lưới an toàn
   autouse** `reset_auth_state()` sau mỗi test trong `conftest.py`.
2. Test concurrency hai thread làm chết kết nối SQLite (transaction mở khi
   exception) → thay bằng kiểm chứng deterministic: conditional-UPDATE là
   nguyên tử của SQLite; test raw rowcount = 0 + API 409.
3. `reset_auth_state()` cần rollback an toàn để không giữ khoá ghi.

## Vòng 3 — sau WP3 (healthz/startup/scripts) + WP6 (mobile web)
**Kiểm chứng:** `test_healthz_open_and_when_auth_enabled` (200 không cookie cả
hai chế độ); trình duyệt thật ở **390×844, 360×800, 768×1024**: không tràn ngang,
button 44 px, input 16 px, chạy trọn lượt soạn ở viewport điện thoại thành công.

**Phát hiện (đã sửa):**
1. **Bug sót từ v3 (tái hiện trong screenshot):** overlay Đăng nhập **luôn
   hiển thị** ở chế độ mở — `.login-overlay{display:flex}` đè thuộc tính
   `hidden` (author CSS thắng UA stylesheet). Sửa:
   `.login-overlay[hidden]{display:none}`; kiểm lại computed style = `none`.
2. iPad 768 px (màn cảm ứng) vẫn zoom-on-focus vì breakpoint 600 px → mở rộng
   rule 16 px lên ≤900 px.
3. Restart server giữa các vòng — tệp log/table lock dư thừa được dọn.

## Vòng 4 — Codex bug-hunt toàn repo (round 2, 15 findings)
**Kiểm chứng:** 15 findings; **14 xử lý**, 1 ghi nhận là giới hạn chấp nhận.

**Đã sửa (tất cả có test/bằng chứng):**
1. `_finish()` set `done` **trước** publish (R2-1 — race SSE treo vĩnh viễn).
2. Setup endpoint: throttle per-IP + fast-reject 409 khi đã có tài khoản
   (R2-3 — chống exhausted CPU bằng PBKDF2).
3. UI: form tài khoản hiện + gửi `setup_token` khi server yêu cầu (R2-4).
4. UI: document rỗng (0 phiên bản, khi pipeline lỗi) không còn làm sập
   `openDocument` (R2-5 — phần JS; dọn DB để dần tự hết).
5. `stream()` cleanup + heartbeat 15 s (R2-6 — patch vòng 1 chưa ăn, xem vòng 1).
6. Edit/restore dùng chung `followRun` có retry-cap; **cả hai nút** khoá khi có
   run đang chạy (R2-7/8 — chống chạy song song → race version).
7. Trùng tên đăng nhập → 400 "Tên đăng nhập đã tồn tại" (R2-9 — trước đây 500).
8. Migration backfill `runs.user_id` từ conversation/document (R2-10 — run cũ
   không thành "mồ côi" 404).
9. Pipeline tự tạo run (CLI) ghi `user_id` (R2-11).
10. Copy off-disk atomic (`.part` → `os.replace`) (R2-12).
11. `?fmt=` lạ → 400 (R2-13); `input[type=password]` 16 px mobile (R2-14).
12. Củng cố 2 test yếu (R2-15): test subscriber gỡ bằng stream thật; test cap
    bucket gọi thẳng `_hit_bucket` (không qua `/api/me`).

**Chấp nhận có ghi nhận (không sửa):** R2-2 (edit/restore đồng thời tính cùng
`MAX(version)+1`) — một nút mỗi tài khoản và UI đã khoá nút khi đang chạy; với
app laptop 1–3 người, rủi ro thực tế thấp; sẽ revisited nếu mở rộng đa người.

**Bug do chính vòng này gây ra (bắt được ngay khi xác minh UI):** callback
generate trong `followRun` dùng chung quên gọi `openDocument` → tài liệu không
tự mở sau khi soạn xong. Sửa + kiểm lại: edit → v2, restore → v3 "Phục hồi từ
v1", nút bật lại đúng.

## Vòng 5 — duyệt chốt
**Kiểm chứng:** pytest **65/65** (Python 3.14) — gồm 17 test mới của v6; eval
**10/10**; trình duyệt: run trọn vẹn + edit + restore + overlay ẩn đúng; JS
`node --check` sạch; `git status` không rác; không bí mật trong các tệp mới
(`web_env.bat` git-ignored; không token nào nằm trong repo).

**Kết luận:** chốt v6. Các bước go-live trên Cloudflare (tunnel/Access/Task
Scheduler) là thao tác tay của chủ tài khoản — liệt kê trong
`docs/DEPLOY.md` + checklist `PLANS_V6.md` §6, kết quả sẽ được ghi nhận khi
chủ nhà chạy.
