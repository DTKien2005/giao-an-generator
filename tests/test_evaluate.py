"""Evaluation harness tests (v1)."""
from app.evaluate import evaluate, load_cases, score_case


def test_eval_set_has_ten_cases():
    cases = load_cases()
    assert len(cases) == 10
    subjects = {c["request"]["subject"] for c in cases}
    grades = {c["request"]["grade"] for c in cases}
    assert len(subjects) >= 3 and len(grades) >= 4, "bộ đánh giá phải đa dạng môn/khối"
    types = {c["request"]["doc_type"] for c in cases}
    assert types == {"lesson_plan", "worksheet"}


def test_full_evaluation_passes_with_mock():
    summary = evaluate(provider="mock", verbose=False)
    assert summary["total"] == 10
    assert summary["passed"] == 10, [
        (r["name"], r["failures"]) for r in summary["results"] if not r["passed"]]


def test_score_case_catches_structural_failures():
    case = {"expected": {"sections": ["objectives", "answers"]}}
    failures = score_case({"sections": {"objectives": ["x"]}}, case, files_ok=True)
    assert any("answers" in f for f in failures)

    # timing out of range is caught
    case2 = {"expected": {"activities_total_minutes": [30, 45],
                          "sections": []}}
    doc2 = {"sections": {"activities": [{"minutes": 60}]}}
    assert any("thời lượng" in f for f in score_case(doc2, case2, files_ok=True))

    # missing diacritics is caught
    case3 = {"expected": {"sections": []}}
    assert any("dấu tiếng Việt" in f for f in
               score_case({"sections": {"assessment": "ok khong dau"}}, case3, files_ok=True))
