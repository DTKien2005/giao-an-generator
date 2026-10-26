"""Generation pipeline (plan §4) and follow-up edit flow (plan §5).

run_full_pipeline: intake → retrieve → writer → (reviewer → reviser)×≤3 → render.
run_edit: classify the edit; small → single-section revise + 1 review round,
large → full loop re-run carrying the edit instruction. Both save every result
as a new version of the same document so the user can diff and roll back.
"""
import json
from datetime import datetime

from . import config, db, keys
from . import prompts
from .formats import default_format_spec
from .providers import ProviderError, generate
from .render_docx import render_docx
from .render_pdf import render_pdf
from .retrieve import search


class MissingInfoError(Exception):
    """Intake found an essential field missing; `args[0]` is the question to ask."""

    def __init__(self, question: str, partial: dict):
        super().__init__(question)
        self.question = question
        self.partial = partial


class PipelineError(Exception):
    pass


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _conversation_user(conversation_id: int) -> int | None:
    row = db.get_conn().execute(
        "SELECT user_id FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    return row["user_id"] if row else None


def _progress(cb, label: str) -> None:
    if cb:
        cb(label)


def _round_payload(run_id: int, round_no: int, role: str, payload: dict) -> None:
    db.get_conn().execute(
        "INSERT INTO run_rounds (run_id, round, role, payload) VALUES (?,?,?,?)",
        (run_id, round_no, role, json.dumps(payload, ensure_ascii=False)),
    )
    db.get_conn().commit()


def _avg_score(review: dict) -> float:
    scores = [s.get("score", 0) for s in review.get("scores", [])]
    return sum(scores) / len(scores) if scores else 0.0


def _has_blocking_issues(review: dict) -> bool:
    return any(i.get("severity") in ("critical", "major") for i in review.get("issues", []))


def save_version(document_id: int, document: dict, format_spec: dict, note: str,
                 render: bool = True) -> int:
    conn = db.get_conn()
    row = conn.execute(
        "SELECT COALESCE(MAX(version), 0) + 1 AS v FROM document_versions WHERE document_id = ?",
        (document_id,),
    ).fetchone()
    version_no = int(row["v"])
    file_docx = file_pdf = None
    if render:
        stem = f"doc{document_id}_v{version_no}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        docx_path = config.GENERATED_DIR / f"{stem}.docx"
        pdf_path = config.GENERATED_DIR / f"{stem}.pdf"
        try:
            render_docx(document, format_spec, docx_path)
            file_docx = str(docx_path)
            render_pdf(document, format_spec, docx_path, pdf_path)
            file_pdf = str(pdf_path)
        except Exception as exc:  # rendering must never lose the content version
            note += f" [lỗi kết xuất: {exc}]"
    cur = conn.execute(
        "INSERT INTO document_versions (document_id, version, content, file_docx, file_pdf, note)"
        " VALUES (?,?,?,?,?,?)",
        (document_id, version_no, json.dumps(document, ensure_ascii=False), file_docx, file_pdf, note),
    )
    conn.execute("UPDATE documents SET latest_version_id = ? WHERE id = ?",
                 (cur.lastrowid, document_id))
    conn.commit()
    return cur.lastrowid


def _update_conversation_summary(conversation_id: int, provider: str | None) -> None:
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE conversation_id = ?"
        " ORDER BY id DESC LIMIT 6",
        (conversation_id,),
    ).fetchall()
    if not rows:
        return
    transcript = "\n".join(f"{r['role']}: {r['content'][:400]}" for r in reversed(rows))
    old = conn.execute("SELECT summary FROM conversations WHERE id = ?",
                       (conversation_id,)).fetchone()["summary"]
    try:
        result = generate(
            [{"role": "system", "content": prompts.SUMMARIZER_SYSTEM},
             {"role": "user", "content": f"Tóm tắt cũ: {old or '(trống)'}\n\nHội thoại mới nhất:\n{transcript}"}],
            prompts.SUMMARY_SCHEMA, provider=provider,
        )
        summary = result["summary"]
    except ProviderError:
        summary = transcript[:500]
    conn.execute("UPDATE conversations SET summary = ?, updated_at = datetime('now') WHERE id = ?",
                 (summary, conversation_id))
    conn.commit()


def _draft_review_revise(intake: dict, format_spec: dict, chunks: list[dict],
                         run_id: int, *, progress=None, provider: str | None = None) -> tuple[dict, dict]:
    """Steps 2–5 of plan §4. Returns (final_document, final_review)."""
    _progress(progress, "Soạn bản nháp…")
    document = generate(
        [{"role": "system", "content": prompts.WRITER_SYSTEM},
         {"role": "user", "content": prompts.writer_user_prompt(intake, format_spec, chunks)}],
        prompts.DOCUMENT_SCHEMA, model=keys.get_model("writer"), provider=provider,
    )
    _apply_request_fields(document, intake)
    _round_payload(run_id, 0, "writer", document)

    final_review = {}
    for round_no in range(1, config.MAX_ROUNDS + 1):
        _progress(progress, f"Thẩm định vòng {round_no}…")
        final_review = generate(
            [{"role": "system", "content": prompts.REVIEWER_SYSTEM},
             {"role": "user", "content": prompts.reviewer_user_prompt(document, format_spec, intake)}],
            prompts.REVIEW_SCHEMA, model=keys.get_model("reviewer"),
            provider=provider, temperature=0.2,
        )
        _round_payload(run_id, round_no, "reviewer", final_review)

        if not _has_blocking_issues(final_review) and _avg_score(final_review) >= config.PASS_SCORE:
            _progress(progress, f"Đạt chuẩn sau vòng thẩm định {round_no}.")
            break
        if round_no == config.MAX_ROUNDS:
            _progress(progress, "Đã hết số vòng thẩm định, dùng bản cuối cùng.")
            break

        _progress(progress, f"Chỉnh sửa theo góp ý vòng {round_no}…")
        document = generate(
            [{"role": "system", "content": prompts.REVISER_SYSTEM},
             {"role": "user", "content": prompts.reviser_user_prompt(document, final_review)}],
            prompts.DOCUMENT_SCHEMA, model=keys.get_model("reviser"), provider=provider,
        )
        _apply_request_fields(document, intake)
        _round_payload(run_id, round_no, "reviser", document)
    return document, final_review


def _apply_request_fields(document: dict, intake: dict) -> None:
    document["grade"] = intake.get("grade", "")
    document["subject"] = intake.get("subject", "")
    if intake.get("week"):
        document.setdefault("week", intake["week"])


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def run_full_pipeline(request: dict, source_text: str, *,
                      conversation_id: int | None = None,
                      user_id: int = 1,
                      progress=None,
                      provider: str | None = None,
                      run_id: int | None = None) -> dict:
    """request may pre-carry grade/subject/lesson/doc_type/week (from the form);
    anything missing is detected from source_text by the intake step.
    `run_id` reuses an existing runs row (web layer creates one up front) instead
    of inserting a duplicate."""
    conn = db.get_conn()

    _progress(progress, "Phân tích yêu cầu…")
    intake = dict(request)
    needs_intake = any(not intake.get(k) for k in ("grade", "subject", "lesson", "doc_type"))
    if needs_intake:
        detected = generate(
            [{"role": "system", "content": prompts.INTAKE_SYSTEM},
             {"role": "user", "content": (source_text or "")[:6000] + "\n\nYêu cầu của giáo viên: "
              + json.dumps({k: v for k, v in intake.items() if v}, ensure_ascii=False)}],
            prompts.INTAKE_SCHEMA, model=keys.get_model("intake"), provider=provider,
        )
        for key, value in detected.items():
            if not intake.get(key):
                intake[key] = value
        question = detected.get("missing") or ""
        essential_missing = [k for k in ("grade", "subject", "lesson") if not intake.get(k)]
        if question or essential_missing:
            raise MissingInfoError(
                question or "Bạn cho biết thêm khối lớp, môn học và tên bài cần soạn nhé?",
                intake,
            )
    doc_type = intake["doc_type"]
    if doc_type not in ("lesson_plan", "worksheet"):
        raise PipelineError(f"doc_type không hợp lệ: {doc_type}")

    _progress(progress, f"Tìm tài liệu tham khảo: {intake['lesson']}…")
    chunks = search(intake["grade"], intake["subject"], f"{intake['lesson']} {doc_type}", k=6)

    format_spec = default_format_spec(doc_type)
    # Plan §3.3: a user-supplied format takes priority over the default.
    user_spec = intake.get("format_spec")
    if user_spec:
        format_spec = json.loads(user_spec) if isinstance(user_spec, str) else user_spec

    # --- persistence: conversation, document, run -------------------------
    if conversation_id is None:
        cur = conn.execute(
            "INSERT INTO conversations (user_id, title) VALUES (?, ?)",
            (user_id, intake["lesson"] or "Tài liệu mới"),
        )
        conversation_id = cur.lastrowid
        conn.commit()
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'user', ?)",
        (conversation_id, (source_text or "")[:4000] or intake["lesson"]),
    )
    conn.commit()

    cur = conn.execute(
        "INSERT INTO documents (conversation_id, title, doc_type, grade, subject, format_spec)"
        " VALUES (?,?,?,?,?,?)",
        (conversation_id, intake["lesson"], doc_type, intake["grade"], intake["subject"],
         json.dumps(format_spec, ensure_ascii=False)),
    )
    document_id = cur.lastrowid
    conn.commit()

    if run_id is None:
        cur = conn.execute(
            "INSERT INTO runs (conversation_id, document_id, user_id, kind, status)"
            " VALUES (?,?,?,?, 'running')",
            (conversation_id, document_id, user_id, "full"),
        )
        run_id = cur.lastrowid
    else:
        conn.execute(
            "UPDATE runs SET conversation_id = ?, document_id = ?, kind = 'full',"
            " status = 'running' WHERE id = ?",
            (conversation_id, document_id, run_id),
        )
    conn.commit()

    # --- draft → review → revise loop (plan §4) ---------------------------
    try:
        document, final_review = _draft_review_revise(
            intake, format_spec, chunks, run_id, progress=progress, provider=provider)

        _progress(progress, "Kết xuất tệp Word và PDF…")
        note = "Bản hoàn chỉnh"
        if final_review:
            note += f" — điểm trung bình {_avg_score(final_review):.1f}"
        version_id = save_version(document_id, document, format_spec, note)

        conn.execute(
            "UPDATE runs SET status = 'done', result_version_id = ?, progress = 'hoàn tất' WHERE id = ?",
            (version_id, run_id),
        )
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'assistant', ?)",
            (conversation_id,
             f"Đã soạn xong {('giáo án' if doc_type == 'lesson_plan' else 'phiếu bài tập')}"
             f" “{intake['lesson']}”. " + (final_review.get("summary", "") if final_review else "")),
        )
        conn.commit()
        _update_conversation_summary(conversation_id, provider)
    except (ProviderError, PipelineError) as exc:
        conn.execute("UPDATE runs SET status = 'error', error = ? WHERE id = ?", (str(exc), run_id))
        conn.commit()
        raise

    return {
        "conversation_id": conversation_id,
        "document_id": document_id,
        "version_id": version_id,
        "document": document,
        "review_summary": (final_review or {}).get("summary", ""),
        "avg_score": _avg_score(final_review) if final_review else None,
    }


# ---------------------------------------------------------------------------
# Follow-up edits (plan §5)
# ---------------------------------------------------------------------------

def run_edit(document_id: int, instruction: str, *,
             progress=None, provider: str | None = None,
             run_id: int | None = None) -> dict:
    conn = db.get_conn()
    doc_row = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if not doc_row:
        raise PipelineError(f"Không tìm thấy tài liệu #{document_id}")
    version_row = conn.execute(
        "SELECT * FROM document_versions WHERE id = ?", (doc_row["latest_version_id"],),
    ).fetchone()
    if not version_row:
        raise PipelineError(f"Tài liệu #{document_id} chưa có phiên bản nào")
    document = json.loads(version_row["content"])
    format_spec = json.loads(doc_row["format_spec"]) if doc_row["format_spec"] else \
        default_format_spec(doc_row["doc_type"])
    summary = conn.execute("SELECT summary FROM conversations WHERE id = ?",
                           (doc_row["conversation_id"],)).fetchone()["summary"]
    intake = {"grade": doc_row["grade"], "subject": doc_row["subject"],
              "lesson": doc_row["title"], "doc_type": doc_row["doc_type"]}

    _progress(progress, "Phân loại yêu cầu chỉnh sửa…")
    classification = generate(
        [{"role": "system", "content": prompts.CLASSIFIER_SYSTEM},
         {"role": "user", "content":
          f"Tóm tắt hội thoại: {summary}\n\nTài liệu: {doc_row['doc_type']} — {doc_row['title']}"
          f"\n\nYêu cầu: {instruction}"}],
        prompts.CLASSIFY_SCHEMA, model=keys.get_model("intake"), provider=provider,
    )
    kind = classification.get("kind", "small")

    conn.execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'user', ?)",
        (doc_row["conversation_id"], instruction),
    )
    if run_id is None:
        cur = conn.execute(
            "INSERT INTO runs (conversation_id, document_id, user_id, kind, status)"
            " VALUES (?,?,?,?, 'running')",
            (doc_row["conversation_id"], document_id, _conversation_user(doc_row["conversation_id"]),
             "small_edit" if kind == "small" else "full"),
        )
        run_id = cur.lastrowid
    else:
        conn.execute(
            "UPDATE runs SET conversation_id = ?, document_id = ?, kind = ?, status = 'running'"
            " WHERE id = ?",
            (doc_row["conversation_id"], document_id,
             "small_edit" if kind == "small" else "full", run_id),
        )
    conn.commit()

    try:
        if kind == "small":
            _progress(progress, "Chỉnh sửa mục bị ảnh hưởng…")
            document = generate(
                [{"role": "system", "content": prompts.REVISER_SYSTEM},
                 {"role": "user", "content":
                  prompts.reviser_user_prompt(document, {
                      "issues": [{"severity": "major", "description": instruction,
                                  "fix": instruction}]}
                  )}],
                prompts.DOCUMENT_SCHEMA, model=keys.get_model("reviser"), provider=provider,
            )
            _apply_request_fields(document, intake)
            _round_payload(run_id, 1, "reviser", document)

            _progress(progress, "Thẩm định lại sau chỉnh sửa…")
            review = generate(
                [{"role": "system", "content": prompts.REVIEWER_SYSTEM},
                 {"role": "user", "content": prompts.reviewer_user_prompt(document, format_spec, intake)}],
                prompts.REVIEW_SCHEMA, model=keys.get_model("reviewer"),
                provider=provider, temperature=0.2,
            )
            _round_payload(run_id, 1, "reviewer", review)
            review_summary = review.get("summary", "")
        else:
            # Large edit (plan §5): full loop again — but on the SAME document,
            # so the result lands as its next version and stays diffable.
            _progress(progress, "Yêu cầu lớn — chạy lại toàn bộ quy trình…")
            chunks = search(intake["grade"], intake["subject"],
                            f"{intake['lesson']} {intake['doc_type']}", k=6)
            full_intake = dict(intake, edit_instruction=instruction)
            document, review = _draft_review_revise(
                full_intake, format_spec, chunks, run_id, progress=progress, provider=provider)
            review_summary = review.get("summary", "")

        _progress(progress, "Kết xuất tệp Word và PDF…")
        version_id = save_version(document_id, document, format_spec,
                                  f"Chỉnh sửa: {instruction[:120]}")
        conn.execute("UPDATE runs SET status = 'done', result_version_id = ? WHERE id = ?",
                     (version_id, run_id))
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'assistant', ?)",
            (doc_row["conversation_id"], f"Đã chỉnh sửa theo yêu cầu: {instruction[:200]}"),
        )
        conn.commit()
        _update_conversation_summary(doc_row["conversation_id"], provider)
    except (ProviderError, PipelineError) as exc:
        conn.execute("UPDATE runs SET status = 'error', error = ? WHERE id = ?", (str(exc), run_id))
        conn.commit()
        raise

    return {
        "conversation_id": doc_row["conversation_id"],
        "document_id": document_id,
        "version_id": version_id,
        "document": document,
        "review_summary": review_summary,
        "kind": kind,
    }
