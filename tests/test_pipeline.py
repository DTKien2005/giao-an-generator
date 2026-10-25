"""Pipeline behaviour with the mock provider: loop convergence and persistence."""
import json
import uuid

from app import db
from app.pipeline import MissingInfoError, PipelineError, run_full_pipeline, run_edit


def _unique_request(doc_type="lesson_plan"):
    return {
        "grade": "grade_1", "subject": "toan",
        "lesson": f"Các số có hai chữ số {uuid.uuid4().hex[:6]}",
        "doc_type": doc_type,
    }


def test_full_pipeline_lesson_plan_converges_and_saves_version():
    result = run_full_pipeline(_unique_request(), "giáo án toán lớp 1", provider="mock")
    assert result["document"]["doc_type"] == "lesson_plan"
    # loop must have run and the final document carries the reviewer-forced appendix
    assert result["document"]["sections"].get("appendix")
    assert result["avg_score"] is not None and result["avg_score"] >= 8.0

    conn = db.get_conn()
    rounds = conn.execute(
        "SELECT role FROM run_rounds WHERE run_id IN"
        " (SELECT id FROM runs WHERE document_id = ?) ORDER BY id",
        (result["document_id"],),
    ).fetchall()
    roles = [r["role"] for r in rounds]
    assert "writer" in roles and "reviewer" in roles
    version = conn.execute(
        "SELECT * FROM document_versions WHERE id = ?", (result["version_id"],)
    ).fetchone()
    assert version["file_docx"] and version["file_pdf"]


def test_full_pipeline_worksheet_has_answers():
    result = run_full_pipeline(
        _unique_request("worksheet") | {"week": "2"},
        "phiếu bài tập tuần 2", provider="mock")
    sections = result["document"]["sections"]
    assert sections.get("exercises") and sections.get("answers")


def test_missing_info_raises_question():
    try:
        run_full_pipeline({"doc_type": "lesson_plan"}, "soạn giúp tôi một bài", provider="mock")
        raised = False
    except MissingInfoError as exc:
        raised = True
        assert exc.question  # one short question, per plan §3.2
    assert raised


def test_bad_doc_type_rejected():
    try:
        run_full_pipeline({"grade": "grade_1", "subject": "toan", "lesson": "x",
                           "doc_type": "sausage"}, "", provider="mock")
        raised = False
    except PipelineError:
        raised = True
    assert raised


def test_small_edit_creates_new_version_of_same_document():
    result = run_full_pipeline(_unique_request(), "", provider="mock")
    doc_id = result["document_id"]
    edit = run_edit(doc_id, "sửa đáp án bài 1 cho đúng", provider="mock")
    assert edit["document_id"] == doc_id  # same document, not a new one
    assert edit["version_id"] != result["version_id"]

    conn = db.get_conn()
    versions = conn.execute(
        "SELECT version FROM document_versions WHERE document_id = ? ORDER BY version",
        (doc_id,)).fetchall()
    assert [v["version"] for v in versions] == [1, 2]
    conv = conn.execute(
        "SELECT summary FROM conversations WHERE id = ?", (result["conversation_id"],)
    ).fetchone()
    assert conv["summary"]  # rolling summary maintained


def test_large_edit_reruns_full_loop_on_same_document():
    result = run_full_pipeline(_unique_request(), "", provider="mock")
    doc_id = result["document_id"]
    edit = run_edit(doc_id, "viết lại toàn bộ giáo án theo hướng khác", provider="mock")
    assert edit["document_id"] == doc_id
    assert edit["kind"] == "large"
    conn = db.get_conn()
    versions = conn.execute(
        "SELECT version FROM document_versions WHERE document_id = ? ORDER BY version",
        (doc_id,)).fetchall()
    assert len(versions) == 2
