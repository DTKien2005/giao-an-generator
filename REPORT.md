# REPORT.md — Session Report & Handoff
**Date:** 2026-10-26 · **Project:** Web_Lam_Giao_An_Bang_Gemini · **Repo:** https://github.com/DTKien2005/giao-an-generator
**This file is the compacted summary of the whole session — a new conversation can resume from here alone.**

---

## 0. v6 in progress (compacted after the implementation round, 2026-10-26)

**Plan:** `PLANS_V6.md` — go-live on `https://giaoan.kinzz-server.io.vn`
(Cloudflare Tunnel + Access, laptop-hosted). Frozen after **5 review cycles**;
cycle 1 was a full Codex (`codex exec` 0.164.0) plan+code review that produced
**25 findings**, the important ones turned into WP0..WP6 below.

**Implemented this round (all offline-verifiable, mock provider):**
- **WP0 security/bug fixes (Codex findings):** run/SSE ownership via new
  `runs.user_id` column (cross-user → 404); upload hardening (basename-only
  filenames, 20 MB cap → 413); format-spec cache now per-user (was hardcoded to
  user 1); `/api/users` + `/api/settings` restricted to the first account when
  auth is on; `_live_runs` capped at 100 finished entries + disconnected SSE
  subscribers removed; `.gitignore` now covers `.env*`, `web_env.bat`, tokens.
- **WP1:** `client_ip()` — trusts `CF-Connecting-IP` only when
  `APP_TRUST_PROXY=1` **and** peer is loopback; validated/normalised with
  `ipaddress`, comma-lists take the first value, garbage falls back to the peer;
  `X-Forwarded-For` never trusted; rate-limit buckets bounded (10 000 clients).
- **WP2:** `APP_SETUP_TOKEN` (constant-time bytes compare) gates
  `POST /api/setup`; atomic sentinel claim (`UPDATE … WHERE password_hash = ''`,
  rowcount-checked, rollback-safe); min password 8; per-IP login throttle
  (20/10 min); `GET /api/me` exposes only `setup_token_required`.
- **WP3:** `GET /healthz` (liveness, no auth/data) + startup reconciliation
  (crashed runs → error) + `scripts/windows/run_web.bat`
  (`127.0.0.1` bind, `APP_TRUST_PROXY=1`, `APP_COOKIE_SECURE=1`, env from
  git-ignored `web_env.bat`, logs to `data/logs/web.log`) +
  `install_tasks.bat`/`uninstall_tasks.bat` (GiaoAnWeb at logon+1 min,
  GiaoAnBackup daily 23:00; idempotent).
- **WP4:** backup zip is atomic (`.part` → integrity check → `os.replace`);
  optional `APP_BACKUP_COPY_DIR` off-disk copy with size verification,
  destination-inside-`data/` rejected, copy failure → non-zero exit without
  touching the local zip.
- **WP6 mobile web (no native app — user decision):** ≤900px layout — 16 px
  inputs (no iOS zoom), 44 px touch targets, full-width buttons, table
  `overflow-x` wrapper; SSE heartbeat 120 s→15 s; EventSource auto-reconnect
  with 20-retry cap; generate/edit buttons stay disabled until the run
  finishes. Verified in-browser at 390×844 / 360×800 / 768×1024: no horizontal
  scroll, form + full run + downloads OK.
- **Leftover bug found by the WP6 verification (from v3):** the login overlay
  was **always visible** in open mode — `.login-overlay{display:flex}` overrode
  the `hidden` attribute; fixed with `.login-overlay[hidden]{display:none}` and
  re-verified in the browser.

**Quality state after this round (final):** 65/65 tests (Python 3.14; CI on 3.12), eval 10/10.
WP5 docs (DEPLOY.md rewritten, README env table) done. Close-out completed in the same session:
final Codex bug hunt (15 more findings — 14 fixed, 1 accepted with rationale,
plus a self-introduced openDocument regression caught and fixed during browser
verification), `reports/v6_review.md` (5 cycles), scientific
`reports/v6_report.md` (2 review passes), `UPDATES.md` v6 entry, tag `v6`.
Remaining: the manual go-live runbook (Cloudflare/Tunnel/Access) which only the
owner can perform on their Cloudflare account (template in v6_report.md §7).

---

## 1. What the project is

A local web app that drafts **Vietnamese lesson plans (giáo án)** and **weekly
worksheets (phiếu bài tập)**: upload/paste source text → intake → retrieve from a
dataset → draft → LLM review → revise (≤3 rounds) → render `.docx`/`.pdf`. All
conversations, document versions and runs are persisted in SQLite for follow-up
chat edits, diffs and rollback. Gemini by default; OpenAI-compatible, Anthropic,
Ollama/local and an offline mock also supported, per role (Writer / Reviewer /
Reviser / Intake).

## 2. Current state (verified)

| Area | State |
|---|---|
| GitHub | `DTKien2005/giao-an-generator`, branch `main`, tags **v1–v5**, CI **green** |
| Tests | **48/48** pass on Python 3.14 (dev) and 3.12 (`py -3.12` venv = CI env) |
| Evaluation | `python -m app.evaluate` → **10/10** cases pass (mock provider) |
| CI | `.github/workflows/ci.yml` runs pytest + eval on every push/PR to `main`, offline (mock), no secrets |
| Docs | `PLANS.md` (design, phases checked off), `PLANS_V1-V5.md`, `UPDATES.md` (full version log), `reports/vN_review.md` + `reports/vN_report.md` for v1–v5, `docs/DEPLOY.md`, `README.md` |

## 3. What was built, chronologically

**v0.x (baseline, commit `b65d80b`)** — scaffold, config, SQLite schema
(users/conversations/messages/documents/document_versions/runs/run_rounds/jobs/chunks/settings),
dataset layout + 6 original seed samples + format templates, ingestion
(headline-based chunking) + hashed/Gemini embeddings + cosine retrieval,
provider layer (Gemini REST + offline mock, validate-JSON-retry-once),
Vietnamese prompts + reviewer rubric, pipeline with 3-round stop rule,
python-docx + reportlab renderers, FastAPI web app with SSE progress,
notebook-styled UI, 33 tests.

**v1 — Evaluation set** (`9482809`): 10 original cases across grades 1–5 and 3
subjects; deterministic rubric (structure, textbook grounding, timing, answers,
diacritics, rendered files); `requirements.txt`.

**v2 — OCR for scanned PDFs** (`ffa21fc`): `app/ocr.py` — pages without a text
layer are rendered at 150 dpi and transcribed by Gemini Vision; safely skipped
with per-page warnings when no key. Gemini request shape covered by a
monkeypatched-httpx test.

**v3 — Multi-user login + backups** (`b84beb8`): progressive auth (open mode
until the first account exists; setup claims the `shared` sentinel user so no
data is orphaned), PBKDF2-SHA256 (240k iterations), 7-day session cookies,
ownership filtering on every data route (cross-user → 404), login overlay UI,
`python -m app.backup` (consistent SQLite snapshot + files + key, keep 10).

**v4 — Rollback + conversation management** (`4cc12e1`): non-destructive restore
(old version's content becomes the new latest version; audit trail/diffs intact),
conversation soft delete (`deleted_at`), UI restore button + hover delete.

**v5 — Docker + CI + deploy** (`0239cbf`, `4105b74`, `0c156e8`): Dockerfile
(python:3.12-slim, non-root, `/srv/data` volume, healthcheck), CI workflow,
`docs/DEPLOY.md` (laptop / Cloudflare Tunnel / Docker / backup schedule /
upgrade). **CI's first run caught a real bug:** the PDF renderer only knew
Windows font paths → on Linux every PDF render failed. Fixed by vendoring **IBM
Plex Serif (OFL)** into `assets/fonts/` (glyph coverage verified via
`has_glyph`), with a bold family mapping; Windows fonts are now only a fallback.

## 4. Process followed (user's standing protocol)

1. Read the two skill folders (karpathy guidelines; docx/pdf/frontend-design)
   and `PLANS.md` before any work.
2. `PLANS_V1-V5.md` drafted → reviewed → remade, **3 documented cycles**.
3. Each version: implement → **review ≥3 cycles** (fix and re-verify on error;
   cycles recorded in `reports/vN_review.md`) → write `reports/vN_report.md`
   → **report reviewed ≥2 cycles** → commit + tag + push.
4. Never touch the user's existing GitHub repos/actions: fresh repo, new
   workflow file only. Credentials via Git Credential Manager (no tokens stored
   in the repo; `data*/` gitignored).
5. Milestones logged in `UPDATES.md` after every version.

## 5. Key decisions & tradeoffs

- **Mock provider** (`[VAI TRÒ: …]` markers in prompts) makes the entire
  pipeline deterministic and offline — CI needs no API keys.
- **Vector store** = embeddings as BLOBs in SQLite + numpy cosine (instead of
  sqlite-vec/Chroma) — small data, no native deps on Windows.
- **Progressive auth** instead of mandatory login — old users unaffected.
- **Vendored font** instead of system-font lookup — rendering identical on
  Windows/Linux/Docker after the CI failure.
- **Non-destructive rollback** — history and diffs never break.
- **Deterministic eval rubric** (no LLM judging) — stable in CI.

## 6. Known limitations / deferred work

- Docker image build not yet run locally (Docker daemon won't start on this
  machine) — Dockerfile is standard; CI runs the same base image.
- Live OCR call not yet exercised with a real key (request shape is tested).
- No password-reset UI (local reset command documented in README).
- Evaluation set is original self-authored samples, not 10 trusted real lessons
  yet; scanned-PDF OCR over real textbooks pending real files.
- Rate limit is per-IP, not per-user; backups are manual/scheduled, not
  monitored.

## 7. How to resume (next conversation)

```bash
python -m pytest tests/ -q          # must be 48/48
python -m app.evaluate              # must be 10/10
```

- New feature versions are **v6+**: extend/imitate `PLANS_V1-V5.md`, write
  `reports/v6_review.md` (≥3 cycles) and `reports/v6_report.md` (≥2 cycles),
  one commit + tag per version, keep CI green, update `UPDATES.md`.
- Auth tests must end with `reset_auth_state()` from `tests/conftest.py` or
  they corrupt the shared test DB.
- Run the app: `python -m uvicorn app.main:app --port 8090` (mock offline) or
  set `GEMINI_API_KEY` / paste a key in the Cài đặt tab.
