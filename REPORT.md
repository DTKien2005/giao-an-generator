# REPORT.md — Session Report & Handoff
**Date:** 2026-10-26 · **Project:** Web_Lam_Giao_An_Bang_Gemini · **Repo:** https://github.com/DTKien2005/giao-an-generator
**This file is the compacted summary of the whole session — a new conversation can resume from here alone.**

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
