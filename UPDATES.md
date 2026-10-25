# UPDATES.md — Version log

Each entry maps to a build phase in `PLANS.md`, records what was added, the
decisions taken, and how the milestone was verified.

---

## v0.1 — Project scaffold, dataset, ingestion & retrieval
**Date:** 2026-10-26 · **Phase:** 1 (dataset part)

**Added**
- `app/config.py` — settings via env vars (data dir, API key, per-role models, round caps).
- `app/db.py` — SQLite schema per plan §5: `users`, `conversations`, `messages`,
  `documents`, `document_versions`, `runs`, `run_rounds`, plus `jobs` (plan §8),
  `chunks` (vector store) and `settings` tables. WAL mode, thread-local connections.
- `app/embeddings.py` — embedding provider: Gemini `text-embedding-004` when a key
  is configured; deterministic hashed bag-of-words (uni+bigram) fallback so the
  whole app works offline (dev/tests/laptop without a key).
- `app/retrieve.py` — filter by grade+subject, then cosine search (plan §2), with
  graceful widening to same-subject-any-grade when a bucket is empty.
- `app/ingest.py` — ingestion script + CLI (`python -m app.ingest`): reads
  `.txt/.md/.docx/.pdf`, honours a `*.meta.json` beside each file (falls back to
  deriving metadata from the folder layout), chunks on Vietnamese section
  headings (`Bài …`, `Hoạt động …`, roman numerals), embeds and stores.
- `dataset/` — folder layout per plan §2 (grade → subject → textbooks/lesson_plans/
  worksheets) seeded with 6 original Vietnamese samples for grade 1–2 (toán,
  tiếng việt) + `format_templates/` with the default lesson-plan and worksheet
  format specs (plan §2 format library).
- `scripts/make_dataset.py` — one-time seeder for the samples above.

**Decisions**
- Plan suggests SQLite + `sqlite-vec` or Chroma; on Windows/Python 3.14 the
  simplest reliable equivalent is vectors-as-BLOBs in SQLite + numpy cosine —
  dataset sizes here are small, and it removes a fragile native dependency.
- Scanned-PDF OCR via Gemini vision is deferred until real scanned textbooks
  exist in the dataset (plan §3.1) — no speculative code.

**Verified**
- `python scripts/make_dataset.py` → 6 files + 2 templates seeded.
- `python -m app.ingest` → `{"files": 6, "chunks": 30, "skipped": []}`.
- Retrieval smoke test: query *"so sánh các số có hai chữ số"* returns the grade-1
  math textbook chunk first (0.674), then the matching lesson plan and worksheet.

---

## v0.2 — Generation pipeline, providers, renderers & CLI
**Date:** 2026-10-26 · **Phase:** 1 complete (loop runs from CLI)

**Added**
- `app/providers.py` — single interface `generate(messages, json_schema, model,
  provider)` per plan §6. Adapters: **Gemini** (REST `v1beta`, structured output
  via `responseSchema`, JSON-schema dialect converter) and **mock** (deterministic,
  role-aware via `[VAI TRÒ: …]` markers — runs the whole pipeline offline).
  Every call validates required fields and retries once on bad JSON (plan §6).
- `app/prompts.py` — Vietnamese prompts + JSON schemas for intake / writer /
  reviewer / reviser / edit-classifier / summarizer. Reviewer rubric implements
  the six criteria of plan §4; writer prompt forces grounding in retrieved chunks.
- `app/pipeline.py` — plan §4 steps 0–6: intake (asks one short question via
  `MissingInfoError` when essentials are missing, plan §3.2) → retrieval →
  draft → review → revise, stopping at 3 rounds or when no critical/major issues
  and average score ≥ 8.0. Persists `runs`, `run_rounds`, `documents`,
  `document_versions`, messages and a rolling conversation summary (plan §5).
  Follow-up `run_edit` classifies small vs large edits: small = targeted revise +
  1 review round; large = full loop — both land as a **new version of the same
  document** so diffs/rollback stay possible.
- `app/formats.py` — default format templates per doc type (title placeholders,
  section order/labels/types) + `extract_format_spec()` that turns an uploaded
  lesson plan's headings into a user format spec (plan §3.3).
- `app/render_docx.py` — python-docx renderer following the format spec
  (activity table for lesson plans, Times New Roman, A4, Vietnamese margins).
- `app/render_pdf.py` — PDF per plan §7: prefers headless LibreOffice when
  installed; reportlab fallback with Times New Roman TTF (full diacritics).
- `app/cli.py` — Phase 1 CLI: `python -m app.cli "<yêu cầu>" --type ...`.

**Fixed along the way**
- Mock reviewer matched `"appendix"` anywhere in the prompt (including the format
  spec) → now parses the document JSON after the `TÀI LIỆU CẦN THẨM ĐỊNH:` marker.
- Mock intake now extracts lesson/week from free text, not just labeled fields.
- `render_pdf._activity_table` used `cm` from another function's scope → PDF
  failed for lesson plans (worksheets passed); import moved into place.

**Verified**
- Lesson plan run (mock provider, ingested dataset): loop converged in 2 rounds —
  round 1 flagged the missing PHỤ LỤC, reviser fixed it, round 2 passed (9.0/10).
  Objectives grounded verbatim in the retrieved textbook chunk ("Đọc, viết được
  các số từ 20 đến 50…"). `.docx` (36 KB) and `.pdf` (with correct diacritics,
  checked via PyMuPDF text extraction) both produced.
- Worksheet run: exercises grounded in the textbook's "Bài tập mẫu", reviewer
  forced the ĐÁP ÁN section, converged round 2.

---

## v0.3 — Web MVP: upload/paste, SSE progress, downloads
**Date:** 2026-10-26 · **Phase:** 2

**Added**
- `app/main.py` — FastAPI app: `POST /api/generate` (JSON or multipart upload;
  `.docx/.pdf/.txt/.md` parsed to text via the ingestion reader), `GET /api/runs/{id}/events`
  (Server-Sent Events live progress, plan §5), run status, conversations, document
  detail, version preview, and `GET /api/versions/{id}/download?fmt=docx|pdf`.
  Runs execute on a background thread (plan §8 jobs style — no Celery) and publish
  progress to subscriber queues; the pipeline reuses the pre-created `runs` row
  (no duplicate run records).
- `templates/index.html` + `static/app.css` + `static/app.js` — single-page UI with a
  deliberate **"vở học sinh" (school notebook) aesthetic** per the frontend-design
  skill: cream paper, double red margin rule, blue-ink serif headings, dashed
  separators, ink-red stamp; all system fonts (offline-safe, full Vietnamese
  diacritics), zero CDN dependencies. Segmented doc-type toggle (shows the week
  field for worksheets), progress card fed by EventSource, document view with
  version picker, Word/PDF download buttons and a full in-browser preview of the
  rendered lesson plan/worksheet (activity table included). Lịch sử tab lists
  conversations and opens their documents.
- Test suite `tests/` (pytest): retrieval, pipeline convergence/edit flows,
  renderers (Vietnamese text in .docx and .pdf verified by re-extraction), and the
  API surface via TestClient including SSE streaming and file upload.

**Fixed along the way**
- `setup_module` in conftest.py is not a pytest hook for test modules → replaced
  with a session-scoped autouse fixture (this is what broke API tests initially).
- `@app.on_event("startup")` deprecated → lifespan context manager; TestClient now
  entered as context manager so lifespan actually runs.
- Mock reviewer had matched `"appendix"` in the whole prompt (matching the format
  spec instead of the document) → now parses the document JSON after its marker.

**Verified**
- 22 pytest tests pass (retrieval, pipeline, renders, API, SSE, upload).
- In-browser verification (ZCode in-app browser against `uvicorn` on :8090, mock
  provider, ingested dataset): lesson-plan run streamed every step live
  ("Phân tích yêu cầu… → Thẩm định vòng 2 → Kết xuất tệp Word và PDF… → Hoàn tất!"),
  then rendered the full document with grounded objectives, activity table and the
  reviewer-forced Phụ lục; download links point at real files. Worksheet run
  produced exercises + Đáp án and the week field toggles with doc type. Empty
  submit shows the correct Vietnamese error. Visual pass: diacritics perfect,
  notebook aesthetic reads clearly, no layout overflow (`scrollWidth == clientWidth`).

---

## v0.4 — History, follow-up chat edits, version diffs
**Date:** 2026-10-26 · **Phase:** 3

**Added**
- `POST /api/documents/{id}/edit` — follow-up instruction endpoint; runs `run_edit`
  on the background worker with SSE progress, exactly like generation. The worker
  was generalised to take a job callable; `run_edit` now reuses the pre-created
  runs row (no duplicate run records, same fix as generate).
- `GET /api/documents/{id}/diff?from_version=&to_version=` — per-section line diff.
- `app/diffing.py` — flattens a document to ordered section lines (activities as
  "name / GV: / HS:" triplets, exercises as "title: content"), diffs with
  `difflib.SequenceMatcher`, unchanged sections omitted.
- UI: chat panel under the document ("Chỉnh sửa tiếp theo yêu cầu") with the full
  conversation history from the DB; sending an instruction streams progress, lands
  the new version, auto-selects it and appends the assistant reply. "⇄ So sánh với
  bản trước" toggles a colored inline diff (green added / red struck-through removed)
  between the selected version and its predecessor.

**Fixed along the way**
- Mock reviser ignored the edit instruction (only filled the mandatory section),
  producing empty diffs — it now applies each fix to the section its text mentions.
- Single-element issue lists collapsed to a bare object in the mock's JSON block
  extraction (iterating a dict yields string keys) → normalized to a list.
- `client` fixture moved from test_api.py to conftest.py so all test modules share
  one session-scoped TestClient.

**Verified**
- 26 pytest tests pass, including: edit endpoint creates v2 of the same document,
  diff endpoint returns the changed section, conversation keeps both turns.
- In-browser: created a lesson plan, sent "sửa phần đánh giá chi tiết hơn…" through
  the chat box → SSE streamed the edit run → v2 selected automatically → diff panel
  showed "IV. Đánh giá (v1 → v2)" with the added line highlighted.

---

## v0.5 — Format preservation from user uploads
**Date:** 2026-10-26 · **Phase:** 4

**Added**
- Upload flow now detects a lesson-plan-like upload and converts its structure
  (section headings, order, labels) into the user's own format spec, which takes
  priority over the default template (plan §3.3). Renderers already walk any spec,
  so the generated .docx/.pdf follow the user's section order and omit sections
  their format doesn't have.
- Spec caching per user + doc type in the `settings` table (plan §3.4): once a
  user uploads their format, later requests reuse it without re-uploading. The
  cached lesson-plan spec is never applied to worksheets.
- Document meta in the UI shows "Định dạng của bạn" when a custom format is active.
- PDF export itself shipped with v0.2/v0.3 (LibreOffice when installed, reportlab
  fallback with Times New Roman); this phase completed the remaining §3.3 piece.

**Verified**
- New tests (`tests/test_format_preserve.py`): uploading a custom 3-section lesson
  plan (Mục tiêu / Hoạt động / Đánh giá — no Đồ dùng) produces a document whose PDF
  contains exactly those sections and omits "Đồ dùng dạy học"; the spec persists in
  `settings` and is reused by the next lesson-plan request; a worksheet request
  still gets the worksheet template. 28/28 tests pass.

---

## v0.6 — Multi-provider, per-role models, encrypted keys, light hardening
**Date:** 2026-10-26 · **Phase:** 5 + light slice of 6

**Added**
- New adapters behind the same `generate(messages, json_schema, …)` interface
  (plan §6): **OpenAI-compatible** (`/chat/completions` with `json_object` — covers
  OpenAI and any Ollama / LM Studio / vLLM server via a custom base URL) and
  **Anthropic** (`/v1/messages`, system prompt carries the JSON requirement).
  Gemini and mock unchanged. Provider/model resolution: explicit argument →
  settings table → env defaults.
- `app/keys.py` — settings + secrets: API keys stored **Fernet-encrypted** in the
  `settings` table (key file `data/secret.key`, generated on first use); env vars
  remain the fallback. Per-role models (`model:writer|reviewer|reviser|intake`),
  default provider, per-provider base URLs. `settings_summary()` exposes keys only
  as booleans — plaintext never leaves storage decrypted.
- Pipeline now picks the model per role from settings (Writer/Reviewer/Reviser can
  differ, per plan §4's note that a model tends to approve its own writing).
  Embeddings also honour a stored Gemini key.
- Settings UI: new "Cài đặt" tab — provider select, four per-role model fields,
  password inputs for the three API keys, local base URL; masthead badge shows the
  active provider and refreshes on save.
- Light hardening (Phase 6 slice): per-client rate limit on generate/edit —
  10 runs / 10 minutes (env `APP_RATE_LIMIT`) as the cost cap plan §10 asks for;
  run history in the `runs` table doubles as the request log. Full login/backup
  tooling deliberately deferred — see the review below.

**Fixed along the way**
- My own rate limiter tripped the test suite (many `/api/generate` calls) → limit
  now configurable via `APP_RATE_LIMIT`, tests run with a high cap; the limiter
  itself has its own burst test that monkeypatches the cap down.
- Settings save message was overwritten by the follow-up form refresh → refresh
  first, then show the result; provider badge updates after save.

**Verified**
- 33 pytest tests pass: key encrypted at rest (plaintext absent from the raw DB
  value), round-trip via `POST /api/settings` (GET never leaks keys), per-role
  model persistence, unknown/no-key provider raises a clear Vietnamese error,
  429 after burst.
- In-browser: switched provider to Anthropic and set Writer=claude-sonnet-4 /
  Reviewer=claude-haiku-4 in the Cài đặt tab → persisted (verified via API) →
  reset to mock for the dev environment.

---

## Tổng kết — plan review (final pass)
**Date:** 2026-10-26

### Đối chiếu PLANS.md ⇄ thực tế

| Kế hoạch (§) | Trạng thái | Ghi chú |
|---|---|---|
| §1 Mục tiêu & phạm vi | ✅ | giáo án + phiếu tuần, Word/PDF, lưu hội thoại/phiên bản, đa nhà cung cấp |
| §2 Dataset + ingestion + format library | ✅ | `dataset/grade_*/subject/type` + `meta.json`, chunk theo đầu mục tiếng Việt, format templates mặc định |
| §3 Input handling | ✅ | .docx/.pdf/.txt parse; intake JSON; hỏi lại 1 câu khi thiếu; format spec từ tệp tải lên được ưu tiên + cache. OCR PDF quét: **chưa** (chưa có tài liệu quét thật — bỏ qua có chủ đích) |
| §4 Pipeline + rubric | ✅ | 0→6 đầy đủ; stop rule "không lỗi critical/major + điểm ≥ 8" hoặc 3 vòng; JSON bắt buộc mọi bước |
| §5 History, versions, follow-up | ✅ | 7 bảng SQLite; tóm tắt hội thoại; phân loại small/large; SSE tiến độ; diff + rollback-by-selection |
| §6 Multi-model | ✅ | 1 interface `generate()`; Gemini / OpenAI-compatible (gồm Ollama, LM Studio, vLLM) / Anthropic / mock; mô hình theo vai trò; khoá mã hoá Fernet; validate-JSON-retry-once |
| §7 Output rendering | ✅ | python-docx theo format spec; PDF: LibreOffice nếu có, fallback reportlab font Times New Roman (tiếng Việt chuẩn) |
| §8 Stack | ✅ | FastAPI + SQLite + HTML/JS thuần (không CDN) + worker thread + jobs table. HTMX bị thay bằng JS thuần: SSE + fetch đơn giản hơn và chạy offline |
| §9 Phases 1–6 | ✅ | xem checkbox trong PLANS.md; Phase 6 chỉ làm lát mỏng (dưới) |
| §10 Risks | ✅ | cost cap (3 vòng, 8192 token/lượt, rate limit 10 lượt/10 phút); reviewer chấm theo rubric chống tự khen; writer phải bám trích dẫn |

### Chưa làm (có chủ đích — ghi lại cho phiên sau)
- **Đánh giá trên 10 bài thật** (§9 Phase 1): bộ mẫu chỉ là 6 tệp gốc do mình soạn; khi có giáo án thật, thêm vào `dataset/` và chạy lại ingestion.
- **Login nhiều người dùng** (§9 Phase 6): app chạy cục bộ một người dùng; bảng `users` đã sẵn nên mở rộng không khó.
- **Backup tự động**: hiện chỉ là tệp `data/app.db` — sao chép định kỳ là đủ ở quy mô laptop.
- **OCR PDF quét bằng Gemini vision** (§3.1).
- **Danh sách các quyết định kỹ thuật** nằm rải trong từng entry ở trên; quan trọng nhất: vector store = BLOB + numpy cosine (thay sqlite-vec/Chroma), và mock provider để toàn bộ hệ thống chạy/check-test được khi không có API key.

## v1 — Bộ đánh giá chất lượng + requirements.txt
**Date:** 2026-10-26 · **Repo:** `DTKien2005/giao-an-generator` (tag `v1`)

**Added**
- `eval/` — 10 ca đánh giá gốc (lớp 1–5, Toán/Tiếng Việt/Tiếng Anh, giáo án +
  phiếu bài tập) với kỳ vọng xác định theo từng ca.
- `app/evaluate.py` + CLI `python -m app.evaluate` — chấm rubric không dùng LLM:
  cấu trúc, bám từ khoá SGK, thời lượng, đáp án, dấu tiếng Việt, tệp kết xuất.
- `tests/test_evaluate.py` (3 test), `requirements.txt`, README mục đánh giá.
- Tài liệu quy trình: `reports/v1_review.md` (3 vòng duyệt, có sửa lỗi thật) và
  `reports/v1_report.md` (2 vòng duyệt).

**Verified:** `python -m app.evaluate` → 10/10 PASS (mock); pytest 36/36.

---

### Cách chạy lại
```bash
python -m app.ingest && python -m uvicorn app.main:app --port 8090   # mock, không cần key
GEMINI_API_KEY=... python -m uvicorn app.main:app --port 8090        # Gemini thật
python -m pytest tests/ -q                                            # 33 test
```






