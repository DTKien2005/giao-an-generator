"""Evaluation harness (PLANS.md §9 Phase 1): run the pipeline over the eval set
and score the output with a DETERMINISTIC rubric — no LLM judging, so results
are stable in CI. Usage:

    python -m app.evaluate [--provider mock]

Cases live in eval/case_NN_{request,expected}.json. A case passes when every
check passes; the run passes when every case passes.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from . import db
from .pipeline import run_full_pipeline

EVAL_DIR = Path(__file__).resolve().parent.parent / "eval"

# Any of these sequences proves the text carries Vietnamese diacritics.
_DIACRITIC_SEQS = ("ế", "ộ", "ị", "ườ", "á", "à", "ộ", "ữ", "ộ", "ượ")


def load_cases() -> list[dict]:
    cases = []
    for request_path in sorted(EVAL_DIR.glob("case_*_request.json")):
        expected_path = request_path.with_name(
            request_path.name.replace("_request.json", "_expected.json"))
        cases.append({
            "name": request_path.name.replace("_request.json", ""),
            "request": json.loads(request_path.read_text(encoding="utf-8")),
            "expected": json.loads(expected_path.read_text(encoding="utf-8")),
        })
    if not cases:
        raise SystemExit(f"Không tìm thấy ca đánh giá nào trong {EVAL_DIR}")
    return cases


def _flatten_text(document: dict) -> str:
    return json.dumps(document, ensure_ascii=False).lower()


def score_case(document: dict, case: dict, files_ok: bool) -> list[str]:
    """Return a list of failure reasons — empty list means the case passed."""
    failures = []
    expected = case["expected"]
    sections = document.get("sections", {})

    for section_id in expected.get("sections", []):
        content = sections.get(section_id)
        if content in (None, "", [], {}):
            failures.append(f"thiếu mục {section_id}")

    text = _flatten_text(document)
    keywords = expected.get("keywords", [])
    if keywords and not any(k.lower() in text for k in keywords):
        failures.append(f"nội dung không bám từ khoá SGK: {keywords}")

    if expected.get("activities_total_minutes"):
        low, high = expected["activities_total_minutes"]
        total = sum(a.get("minutes", 0) for a in sections.get("activities", []))
        if not low <= total <= high:
            failures.append(f"tổng thời lượng hoạt động {total} ngoài [{low}, {high}]")

    min_answers = expected.get("min_answers_chars")
    if min_answers and len(str(sections.get("answers", ""))) < min_answers:
        failures.append("đáp án quá ngắn hoặc thiếu")

    if not re.search("|".join(_DIACRITIC_SEQS), text):
        failures.append("văn bản thiếu dấu tiếng Việt")

    if not files_ok:
        failures.append("chưa kết xuất được docx/pdf")

    return failures


def evaluate(provider: str = "mock", verbose: bool = True) -> dict:
    db.init_db()
    results = []
    for case in load_cases():
        request = dict(case["request"])
        result = run_full_pipeline(request, "", provider=provider)
        document = result["document"]
        version = db.get_conn().execute(
            "SELECT file_docx, file_pdf FROM document_versions WHERE id = ?",
            (result["version_id"],)).fetchone()
        files_ok = all(
            version[field] and Path(version[field]).exists()
            for field in ("file_docx", "file_pdf"))
        failures = score_case(document, case, files_ok)
        results.append({
            "name": case["name"],
            "lesson": request["lesson"],
            "passed": not failures,
            "failures": failures,
            "avg_score": result.get("avg_score"),
        })
        if verbose:
            status = "PASS" if not failures else "FAIL"
            print(f"  [{status}] {case['name']}: {request['lesson']}")
            for failure in failures:
                print(f"         - {failure}")
    passed = sum(1 for r in results if r["passed"])
    if verbose:
        print(f"\nKết quả: {passed}/{len(results)} ca đạt.")
    return {"results": results, "passed": passed, "total": len(results)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chạy bộ đánh giá chất lượng")
    parser.add_argument("--provider", default=None)
    args = parser.parse_args()
    summary = evaluate(args.provider or None)
    sys.exit(0 if summary["passed"] == summary["total"] else 1)
