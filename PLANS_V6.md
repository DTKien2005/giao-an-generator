# PLANS_V6.md — Go-Live: Deploying to `kinzz-server.io.vn`

> Follows the same process as `PLANS_V1-V5.md`: plan → review → rework (≥3 cycles
> before the plan is frozen), then implement → review the code (≥3 cycles) →
> write `reports/v6_report.md` (reviewed ≥2 cycles) → one commit + tag `v6` + push.
> Repo: `DTKien2005/giao-an-generator`, branch `main`.

## 0. Goal and non-goals

**Goal:** make the app reachable at `https://giaoan.kinzz-server.io.vn` from the
owner's phone and other devices, safely, running from the laptop, starting by
itself after a reboot, with daily off-disk backups.

**Non-goals (deferred):**

- Public sign-ups or any open access (the dataset may contain copyrighted
  textbooks; access stays private, see PLANS.md §10).
- Moving to a VPS or mini PC (the move is documented, not performed).
- Docker on this machine (the Docker daemon does not start here; run from a venv).
- Password-reset UI, per-user rate limits, backup monitoring (still on the
  deferred list from `REPORT.md` §6).

## 1. Starting state (from `REPORT.md`, verified before work begins)

| Area | State |
|---|---|
| Code | v1–v5 tagged, CI green, 48/48 tests (Python 3.12 = CI env), eval 10/10 |
| Domain | `kinzz-server.io.vn` on Cloudflare (Free); nameservers changed and confirmed via `nslookup`; zone may still show *Pending* until Cloudflare re-checks |
| Old DNS | A/AAAA/MX records imported from the registrar still exist and must be cleaned up |
| App | Runs locally with `python -m uvicorn app.main:app --port 8090`; auth is "progressive" (open until the first account exists) |
| Hosting | Laptop first; Cloudflare Tunnel as the front door |

## 2. Definition of Done (inherited, plus v6 specifics)

- All pytest green (old + new) on Python 3.12; `python -m app.evaluate` 10/10.
- Existing GitHub workflows untouched; `ci.yml` stays green.
- No secrets in the repo (`data*/`, `.env`, tunnel tokens are git-ignored).
- Every new code path works with the `mock` provider (CI needs no keys).
- `README.md`, `UPDATES.md` and `docs/DEPLOY.md` updated.
- `reports/v6_review.md` (≥3 cycles), `reports/v6_report.md` (≥2 cycles), tag `v6`.
- The go-live checklist in §6 is fully ticked on the real domain.

## 3. Work packages

### WP0 — Security & bug fixes found by the Codex plan review (code, first)

Direct fixes from the review pass (details in `reports/v6_review.md`):

1. **Run/SSE ownership** (Codex R1-1, highest): `GET /api/runs/{id}` and the SSE
   stream must verify ownership (runs → conversations → user); non-owners get
   404. In open mode everything stays accessible as today.
2. **Upload hardening** (Codex R1-5): sanitise the client filename
   (`Path(name).name`, reject `..`/absolute), cap upload size (20 MB) and reject
   oversized uploads with a clear message.
3. **Format-spec cache per user** (Codex R1-10): use the requesting user's id,
   not the hardcoded `1`.
4. **Settings/user creation restricted to the first account** (Codex R1-2):
   `POST /api/users` and `POST /api/settings` require `user_id == 1` when login
   is enabled; open mode unchanged.
5. **`_live_runs` pruning + subscriber cleanup** (Codex R1-14): finished runs
   are pruned (cap 100, oldest finished first); disconnected SSE subscribers are
   removed from their queue list.
6. **`.gitignore`**: add `.env`, tunnel-token patterns, `scripts/windows/web_env.bat`
   (Codex R1-4) and verify with `git check-ignore`.

**Acceptance:** a test proves a second user cannot read another user's run/SSE
(404), traversal filenames are neutralised, oversized uploads get 400/413, and
all pre-existing tests stay green.

### WP1 — Client IP behind the tunnel (code)

**Why:** the rate limit is per IP (`APP_RATE_LIMIT`, default 10 runs / 10 min).
Behind `cloudflared`, every request likely arrives from `127.0.0.1`, so the
limit would become one shared bucket. This needs to be confirmed first, then fixed.

**Tasks**

1. Add a `client_ip(request)` helper. Only when `APP_TRUST_PROXY=1` **and** the
   direct peer is loopback, use the `CF-Connecting-IP` header; otherwise use the
   socket peer. Never trust the header from non-loopback peers, and never trust
   `X-Forwarded-For` (attacker-settable) — Cloudflare sets `CF-Connecting-IP`.
2. **Validate the header before use** (Codex R1-8): take only the first value if
   a comma list arrives, require it to parse as a valid IPv4/IPv6 address
   (`ipaddress.ip_address`), otherwise fall back to the socket peer. Normalise
   through `ipaddress` so equivalent forms share one bucket.
3. **Bound the bucket storage** (Codex R1-8/9): when `_run_times` exceeds 10 000
   clients, drop the oldest buckets. Malformed requests that fail validation
   before the rate-limit check do not consume quota.
4. Use the helper everywhere the app reads the client IP (rate limit, logs).
5. Tests: header ignored when the flag is off; header ignored from a non-loopback
   peer; header used when both conditions hold; rate-limit buckets separate
   by forwarded IP; multi-value and garbage headers fall back safely; bucket
   map stays bounded.

**Acceptance:** new tests pass; behaviour with the flag off is unchanged.

### WP2 — Close the first-account race (code, small)

**Why:** in "open mode", `POST /api/setup` is callable by anyone who can reach
the site. Exposing the app before the first account exists lets a stranger claim
it (and spend the Gemini key).

**Tasks**

1. Optional env var `APP_SETUP_TOKEN`. When set, `/api/setup` requires it
   (constant-time compare via `hmac.compare_digest`; the token is never logged
   or echoed); when unset, behaviour is unchanged.
2. **Atomic claim** (Codex R1-3): `setup_first_user` claims the sentinel with
   `UPDATE users SET ... WHERE id = 1 AND password_hash = ''` and checks the
   rowcount — two concurrent setups cannot both win. A concurrency test runs two
   setup attempts in parallel and asserts exactly one succeeds.
3. The Settings → Account form shows a token field only when the server reports
   that one is required (new boolean `setup_token_required` in `GET /api/me`;
   never reveal the token itself).
4. **Minimum password length 8** on setup and on creating additional users
   (Codex R1-7). Login gets a small per-IP throttle (reuse the rate-limit
   bucket; 20 attempts / 10 min) — Codex R1-7.
5. Tests: setup rejected without or with a wrong token (403); accepted with the
   right token; unchanged when the variable is unset; short passwords rejected;
   concurrency test above; tests end with `reset_auth_state()` and clear the env.

**Acceptance:** with the token set, a stranger cannot create the first account;
two concurrent setups yield exactly one winner. The procedural rule (create the
account **before** exposing the app) stays in the runbook as the primary defence.

### WP3 — Health check and startup scripts (ops)

1. `GET /healthz` — **liveness only** (Codex R1-24): no auth even when login is
   enabled, no data returned beyond `{"ok": true}`, no DB call, target < 100 ms.
   The Dockerfile healthcheck is switched to it. Tested with and without auth
   enabled.
2. **Startup reconciliation** (Codex R1-11): on lifespan startup, mark any
   `runs` rows still `queued`/`running` as `error` ("ứng dụng khởi động lại giữa
   chừng") so no run is stuck forever after a crash/reboot.
3. `scripts/windows/run_web.bat` — activates `.venv`, binds to `127.0.0.1:8090`
   (Codex R1-23: tunnel origin must use `127.0.0.1`, not `localhost`, which may
   resolve to IPv6), sets `APP_TRUST_PROXY=1`, `APP_COOKIE_SECURE=1`,
   `APP_SETUP_TOKEN` / `APP_BACKUP_COPY_DIR` read from a local
   `scripts\windows\web_env.bat` (git-ignored) because scheduled tasks do not
   inherit interactive env vars (Codex R1-21), logs to `data\logs\web.log`.
4. `scripts/windows/install_tasks.bat` — registers two Task Scheduler jobs:
   - `GiaoAnWeb`: at logon (with 1-minute delay), runs `run_web.bat` via the
     venv's `python.exe` by absolute quoted path; the bat starts by verifying the
     project drive exists (Codex R1-21/23). At-logon is accepted for this laptop
     pilot (VPS move is a documented non-goal; pre-logon availability would need
     a Windows service — out of scope).
   - `GiaoAnBackup`: daily 23:00, runs `python -m app.backup` and the off-disk copy.
   Both jobs are removed and re-added on reinstall (idempotent).
5. `scripts/windows/uninstall_tasks.bat` — removes both jobs.

**Acceptance:** after a reboot and login, the site answers without any manual step.

### WP4 — Off-disk backup copy (code + docs)

**Why:** a backup on the same disk does not survive disk failure. The zip also
contains the encryption key, so it must not go to a public place.

**Tasks**

1. **Atomic local zip** (Codex R1-18): write to `backup_<stamp>.zip.part`, verify
   the archive opens with `zipfile` and contains `app.db`, then `os.replace` to
   the final name; on any exception remove the `.part` and re-raise.
2. Optional `APP_BACKUP_COPY_DIR`: after the zip is final, copy it to that
   directory (a synced Drive/OneDrive folder or USB path) and verify the copy by
   byte size. Rejected: a destination inside the project's `data/` directory
   (Codex R1-20). A failed copy is logged and makes the CLI exit non-zero, but
   never deletes or corrupts the local zip. Retention (10 local zips) unchanged.
3. **Confidentiality rule** (Codex R1-17): the zip contains the encryption key —
   the copy destination must be private and access-controlled; documented in
   DEPLOY.md and the checklist (no public/shared links).
4. Document and manually verify a **restore drill**: stop the app → unzip into a
   fresh `APP_DATA_DIR` → start → conversations and versions visible **and** a
   rendered `.docx` downloads and the stored API key still decrypts (Codex R1-19).
5. Tests: atomic naming (no `.part` left on success), copy happens when the
   variable is set, missing/invalid directory exits non-zero without touching
   the local zip, destination inside `data/` is rejected; retention unchanged.

**Acceptance:** restore drill succeeds on a clean folder; recorded in the report.

### WP6 — Mobile web (code + CSS, no native app)

**Why:** the owner will use the site from a phone through Cloudflare Access.
There is **no native/mobile app** (user decision 2026-10-26; the Android skills
library stays unused) — the requirement is that the existing web UI works well
on mobile browsers.

**Tasks**

1. **Spec** (Codex R1-25): primary viewport 390×844 (iPhone-ish), secondary
   768×1024 (tablet) and 360×800 (small Android); touch targets ≥ 44 px;
   document body readable without zoom; no horizontal page overflow at any of
   the three widths; the activity table scrolls inside its own `overflow-x`
   wrapper instead of stretching the page.
2. CSS: tighten the ≤900px layout — single-column form, full-width buttons,
   larger inputs (16 px font to avoid iOS zoom-on-focus), `.doc-body` tables
   wrapped in `.table-scroll`, chat input row stays usable, version actions wrap.
3. JS: **SSE resilience on mobile** (Codex R1-13/12) — `EventSource` auto-retries
   if `onerror` does not close it; cap auto-retries at 20, then surface an error
   line. Server heartbeat drops from 120 s to **15 s** (well under Cloudflare's
   read timeout). Generate/edit buttons stay disabled until the run finishes
   (Codex R1-15) to stop mobile double-taps causing parallel Gemini runs.
4. Verify in a real browser at all three viewports: form usable, run completes,
   document renders, downloads offered, no page-level horizontal scroll.

**Acceptance:** the three-viewport browser check passes and is recorded in the
report; all tests stay green.

### WP5 — Documentation

1. Rewrite `docs/DEPLOY.md` around the exact flow in §5 (venv on Windows,
   Cloudflare Tunnel, Access, Task Scheduler, backups, upgrade, rollback),
   including the **runbook order fix**: the tunnel hostname must not be treated
   as reachable until the Access policy exists (Codex R1-16) — configure Access
   immediately after creating the hostname, before testing from any device.
2. Add a short "Moving to a VPS / mini PC" section: copy `data/` or restore a
   backup, reinstall the tunnel with the same token, no DNS change.
3. Update `README.md` (environment-variable table: `APP_TRUST_PROXY`,
   `APP_SETUP_TOKEN`, `APP_BACKUP_COPY_DIR`, `APP_COOKIE_SECURE`) and `UPDATES.md`.
4. Document the accepted security posture from the Codex review: per-IP login
   throttle + min password length added; cookie `Secure` flag set in production
   (`APP_COOKIE_SECURE=1`); SameSite=Lax documented as the CSRF mitigation for a
   private Access-gated deployment with no sibling subdomains; settings and user
   creation restricted to the first account (Codex R1-2).

## 4. Architecture at go-live

```
Phone / other device
   │  HTTPS
   ▼
Cloudflare edge ── Access policy (owner's email, one-time code)
   │  tunnel (outbound only; no open ports on the laptop)
   ▼
cloudflared (Windows service)
   │  http://localhost:8090
   ▼
uvicorn app.main:app  (bound to 127.0.0.1)
   ├─ SQLite + generated files + encryption key in ./data
   └─ Gemini API (key stored encrypted, or GEMINI_API_KEY env var)
```

Two independent layers protect the site: **Cloudflare Access** blocks strangers
at the edge; the **app's own login** separates users and data inside.

## 5. Go-live runbook (manual steps, in order)

### Phase 0 — Run it for real on the laptop (still private)

```powershell
cd H:\Web_Lam_Giao_An_Bang_Gemini
git pull
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest tests/ -q            # must be all green
python -m app.ingest
python -m uvicorn app.main:app --host 127.0.0.1 --port 8090
```

1. Open `http://127.0.0.1:8090`, paste the Gemini key in Settings, and run one
   real lesson plan end to end.
2. **Create the first account now** (Settings → Account), before any exposure.

### Phase 1 — Domain and tunnel

1. Cloudflare → Overview shows **Active** (click *Check nameservers now* if not).
2. DNS → Records: delete the old A and AAAA records for the root and `www`;
   keep MX only if mail on this domain is in use.
3. Zero Trust → Networks → Tunnels → Create → Cloudflared → Windows; run the
   install command in an **Administrator** PowerShell (installs a service).
4. Public Hostname: `giaoan` + `kinzz-server.io.vn` → `HTTP` →
   `localhost:8090`.

### Phase 2 — Lock the front door

Zero Trust → Access → Applications → Self-hosted → hostname
`giaoan.kinzz-server.io.vn`, policy: allow only the owner's email(s). Free plan
covers up to 50 users. Add further emails to the policy to share access.

### Phase 3 — Survive reboots

1. Run `scripts\windows\install_tasks.bat` (WP3).
2. Windows power settings: sleep = Never while plugged in; disable hibernate.
3. Make sure drive `H:` is present at logon (the task fails if it is not).

### Phase 4 — Backups

1. Set `APP_BACKUP_COPY_DIR` to a synced or external folder.
2. Run `python -m app.backup` once by hand, check the zip and the copy.
3. Perform the restore drill (WP4).

### Phase 5 — Verify (checklist in §6)

## 6. Go-live acceptance checklist

- [ ] Cloudflare zone is **Active**; old A/AAAA records are gone.
- [ ] From a phone on mobile data: Access prompt → code by email → app login.
- [ ] A stranger (private window, other email) is blocked by Access.
- [ ] One real Gemini run with all 3 rounds completes; the SSE progress bar does
      not stall and Cloudflare returns no 524.
- [ ] `.docx` and `.pdf` download correctly; Vietnamese diacritics are intact.
- [ ] Chat edit, diff view and version restore work through the public URL.
- [ ] Rate limit buckets are per real client IP, not one shared bucket (WP1).
- [ ] After a full reboot and login, the site returns without manual steps.
- [ ] Daily backup runs; a copy exists off the disk; restore drill passed.
- [ ] A spending cap or quota is set on the Gemini key (Google AI Studio / Cloud).
- [ ] A scanned PDF is run through OCR with the real key (still unverified).
- [ ] Mobile (no native app — mobile web only): form usable, run completes,
      document renders and downloads at 390×844 / 360×800 / 768×1024; no
      page-level horizontal scroll; SSE survives a brief network switch.

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Stranger claims the first account while in open mode | Create the account in Phase 0; optional `APP_SETUP_TOKEN` (WP2) |
| Laptop sleeps, loses power or network → site down | Power settings; accept for the pilot; move to mini PC/VPS when uptime matters |
| Cloudflare ~100 s request timeout (524) | Pipeline runs in the background and streams SSE; verified in the checklist with a full 3-round run |
| Shared rate-limit bucket behind the tunnel | WP1 (`CF-Connecting-IP`, trusted only from loopback) |
| Backup lost together with the disk, or leaked (contains the key) | Off-disk copy to a private location; restore drill |
| Gemini cost overrun | Quota/spend cap on the key; app-level rate limit and round cap |
| Copyrighted textbooks in the dataset | Private access only (Access + login); no public launch without a rights check |
| Old A/AAAA records conflict with the tunnel's CNAME | Delete them in Phase 1 |

## 8. Versioning and commit plan

- One commit for v6 (code + tests + scripts + docs + reports + `UPDATES.md`),
  then tag `v6`. Never rewrite pushed history.
- Suggested internal order: **WP0 → WP1 → WP2 → WP4 → WP3 → WP6 → WP5**; run the
  full test suite and the evaluation after each package, and update
  `REPORT.md`'s "current state" after each implemented package (session compaction).
- The go-live phases (§5) are performed after the code is merged and CI is green,
  then recorded in `reports/v6_report.md` with the date, results of the checklist
  and any deviations.

## 9. Plan review log — 5 cycles (Codex as planning reviewer + self-review)

### Cycle 1 — Codex full plan + code review (2026-10-26, `codex exec` 0.164.0)
- **Findings:** 25 items (see the codex transcript in `reports/v6_review.md`).
  Highest-impact: missing ownership check on run/SSE endpoints (R1-1); any user
  can change global settings/create users (R1-2); setup race is not closed by a
  token alone — needs an atomic claim (R1-3); upload path traversal + no size
  cap (R1-5); format-spec cache hardcoded to user 1 (R1-10); stuck runs after a
  crash (R1-11); SSE heartbeat 120 s ≈ Cloudflare's read timeout (R1-12);
  `onerror` kills EventSource auto-reconnect (R1-13); `_live_runs`/queues leak
  memory (R1-14); buttons re-enable before the run finishes (R1-15); tunnel
  hostname published before Access exists (R1-16); backup zip non-atomic (R1-18);
  scheduled tasks don't inherit env vars / mapped-drive & localhost pitfalls
  (R1-21/22/23); `/healthz` undefined (R1-24); "mobile" had no acceptance spec
  (R1-25).
- **Changes made:** plan rewritten — new **WP0** (direct security/bug fixes),
  WP1/WP2/WP3/WP4 hardened with the acceptance criteria above, **WP6 mobile web**
  added (user decision: no native app), runbook order fixed (Access before
  exposure), checklist extended.

### Cycle 2 — self-review with the security-audit skill (WEB-PROTOCOL-AND-AUTH)
- **Findings:** WP1 must never trust `X-Forwarded-For` (attacker-settable; only
  `CF-Connecting-IP` from a loopback peer) — plan updated. Cookie hardening needs
  a production-only `Secure` flag (`APP_COOKIE_SECURE=1`) because dev runs over
  plain http on 127.0.0.1 — added to WP3's bat + WP5 docs. SameSite=Lax recorded
  as the CSRF mitigation with its scope (private Access-gated app, no sibling
  subdomains) — added to WP5's posture paragraph. `hmac.compare_digest` and
  never-echo rules made explicit for the setup token.
- **Changes made:** WP1 rule 1, WP2 task 1, WP3 task 3, WP5 task 4 updated.

### Cycle 3 — self-review of operability (Windows specifics)
- **Findings:** scheduled tasks need a durable env source → `web_env.bat`
  (git-ignored); `schtasks` cannot express restart-on-failure cleanly → accept
  at-logon + 1-minute delay and document the laptop-pilot limit; tunnel origin
  must be `http://127.0.0.1:8090`; backup copy needs measurable rejection rules
  (destination inside `data/` refused) and a non-zero exit code on copy failure.
- **Changes made:** WP3 tasks 3–4, WP4 tasks 2/5, §6 checklist wording.

### Cycle 4 — self-review of the mobile-web spec (user's mid-turn decision)
- **Findings:** "mobile web, no app" needs concrete viewports and behaviours:
  390×844 / 360×800 / 768×1024; 16 px inputs (iOS zoom-on-focus); ≥44 px touch
  targets; `overflow-x` wrapper for the activity table (currently stretches the
  page — confirmed against `static/app.css`); SSE must survive a network switch
  (auto-reconnect) — ties to Codex R1-13; buttons must not allow parallel runs.
- **Changes made:** WP6 written with the spec + verification method (browser at
  three viewports, DOM measurement, recorded in the report).

### Cycle 5 (freeze)
- **Final checks:** every WP has testable acceptance; everything new is
  verifiable offline with the mock provider (mobile check is the one manual
  browser verification, recorded with evidence); no secrets in the repo
  (`web_env.bat` + `.env` git-ignored from WP0-6); scope contains nothing the
  user excluded (no native app, no VPS move, no Docker on this laptop);
  implementation order WP0→WP1→WP2→WP4→WP3→WP6→WP5 with tests + eval + REPORT.md
  compaction after each package; Codex remains reviewer for the bug hunt on the
  final code.
- **Decision:** plan frozen.
