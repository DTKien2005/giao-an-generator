# PLANS.md — AI Lesson Plan & Weekly Worksheet Generator (Vietnamese)

## 1. Goal and scope

A web app that drafts **lesson plans (giáo án)** and **weekly worksheets (phiếu bài tập tuần)** in Vietnamese, using the Gemini API by default.

- **Input:** an uploaded Word or PDF file, or long pasted text.
- **Knowledge base:** a dataset folder organized by grade, subject, and document type.
- **Core loop:** retrieve context → draft → review → revise, repeated up to 3 rounds.
- **Output:** a downloadable `.docx` or `.pdf`.
- **Persistence:** all conversations and document versions are saved, so a user can return and ask for further edits to the same file.
- **Models:** Gemini first; later ChatGPT (OpenAI), Claude, and local models, chosen by the user.

---

## 2. Dataset layout

```
dataset/
  grade_1/
    toan/
      textbooks/        # SGK, sách giáo viên
      lesson_plans/     # sample giáo án in the standard format
      worksheets/
    tieng_viet/
      ...
  grade_2/
    ...
```

- Put a small `meta.json` next to each file: grade, subject, book series, lesson number, document type.
- **Ingestion script:**
  1. Convert each file to clean text/Markdown.
  2. Chunk it by lesson or section.
  3. Embed the chunks (Gemini embeddings work fine).
  4. Store them in a vector index (SQLite + `sqlite-vec`, or Chroma).
- **Retrieval:** filter by grade and subject first, then semantic search. This keeps prompts small and relevant.
- **Format library:** keep 1–2 default format templates per document type. These are the fallback when the user brings no format of their own.

---

## 3. Input handling

1. Parse `.docx` with `python-docx` and PDFs with PyMuPDF or pdfplumber. For scanned PDFs, send page images to Gemini vision for OCR.
2. **Intake step** (LLM, JSON output): detect grade, subject, lesson title, and document type. If something essential is missing, ask the user one short question.
3. **Format detection:**
   - If the upload looks like a lesson plan, extract its structure into a *format spec* (section headings, order, table layout). This is "the user's format" and **takes priority**.
   - If the input is plain text or has no clear structure, use the default dataset template.
4. Cache each user's extracted format spec so they do not have to re-upload it.

---

## 4. Generation pipeline

| Step | Role | Output |
|------|------|--------|
| 0 | Intake | Structured request (JSON) |
| 1 | Retriever | Top-k chunks from the dataset |
| 2 | Writer | Draft v1, following the format spec |
| 3 | Reviewer | JSON: score per criterion, issues with severity, concrete fixes |
| 4 | Reviser | Draft v2 that addresses every issue |
| 5 | Repeat 3 → 4 | Stop after 3 rounds, or earlier if there are no critical issues and the score passes a threshold |
| 6 | Renderer | `.docx` and `.pdf` |

**Reviewer rubric**

- Alignment with the curriculum and textbook content
- Factual and language accuracy (Vietnamese spelling and grammar)
- Age-appropriate difficulty
- Realistic timing of activities
- Compliance with the format spec
- Variety of exercises and a clear answer key (worksheets)

**Design notes**

- Give the Reviewer a different prompt from the Writer, and ideally a different model, because a model tends to approve its own writing.
- Always require structured JSON output so the loop can run automatically.
- The Reviewer should flag real problems only, not style preferences; this keeps the loop from rewriting forever.

---

## 5. History, versions, and follow-up edits

**Database tables**

- `users`
- `conversations`
- `messages`
- `documents`
- `document_versions` (full content + file path)
- `runs` (one per pipeline execution)
- `run_rounds` (draft, review, revision for each round)

**Follow-up flow**

- Load the latest document version plus a conversation summary; do not replay the whole history.
- Classify the edit:
  - **Small targeted change:** edit only that section and run 1 review round.
  - **Large rewrite:** run the full loop.
- Save every result as a new version so the user can view diffs and roll back.
- Show live progress in the UI ("Drafting… Reviewing round 1… Revising…") using Server-Sent Events.

---

## 6. Multi-model support

- Define one interface: `generate(messages, json_schema, model)`.
- Adapters: Gemini, OpenAI, Anthropic, and any OpenAI-compatible local server (Ollama, LM Studio, vLLM). Write them yourself, or use LiteLLM to save time.
- In settings, let the user choose a model **per role** (Writer, Reviewer, Reviser) and paste their own API key. Encrypt stored keys.
- Caveats:
  - Structured-output support differs between providers.
  - Small local models are often noticeably weaker in Vietnamese.
  - Wrap every call with "validate JSON, then retry once".

---

## 7. Output rendering

- **Word:** fill the user's own `.docx` as a template (`docxtpl` or `python-docx`) whenever they uploaded one; otherwise use the default template.
- **PDF:** convert the `.docx` with headless LibreOffice so the Word and PDF files always match.
- Test Vietnamese fonts, tables, and diacritics early.

---

## 8. Suggested stack (simple for a first build)

- **Backend:** Python + FastAPI
- **Database:** SQLite (move to Postgres later if needed)
- **Frontend:** plain HTML + HTMX to start, or Next.js if you prefer React
- **Jobs:** a simple background worker with a jobs table (no Celery yet)
- **Hosting:** run on the laptop first and expose it through a Cloudflare Tunnel on your domain; move to a VPS or mini PC only when you need uptime

---

## 9. Build phases

- [x] **Phase 1 — Dataset and prompts (no web):** organize the folders, write the ingestion script, run the Writer → Reviewer → Reviser loop from a CLI. Test on 10 real lessons you already trust; this is the evaluation set. *(v0.1–v0.2; evaluation set = 6 seeded samples + mock provider until real lessons are added)*
- [x] **Phase 2 — Web MVP:** upload or paste, run the pipeline with Gemini, show progress, download `.docx`. *(v0.3)*
- [x] **Phase 3 — History and versions:** database, chat UI, targeted edits, diffs. *(v0.4)*
- [x] **Phase 4 — Format preservation:** detect and reuse the user's own layout; add PDF export. *(v0.5; PDF via LibreOffice when installed, reportlab fallback otherwise)*
- [x] **Phase 5 — Multi-provider:** adapters, per-role model settings, local model support. *(v0.6)*
- [x] **Phase 6 — Hardening:** login, rate limits, cost caps (max rounds, max tokens), logging, backups. *(light slice in v0.6: rate limit + cost caps + run log; login and backups deferred — see UPDATES.md review)*

---

## 10. Risks and early decisions

- **Copyright:** textbooks in the dataset are copyrighted. Fine for private use, but check before opening the site to the public.
- **Cost and rate limits:** each request makes about 7–10 model calls (intake + 3 rounds of draft/review/revise). Set a hard cap and watch the Gemini free-tier limits.
- **Review loops that do not converge:** use the stop rule (no critical issues, or 3 rounds max).
- **Hallucinated curriculum details:** require the Writer to ground every learning objective in retrieved chunks, and let the Reviewer reject anything unsupported.
