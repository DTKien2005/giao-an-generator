# One-time seeder for the evaluation set (eval/) — 10 original Vietnamese cases.
# Each case: NN_request.json (pipeline input) + NN_expected.json (deterministic
# rubric expectations). "keywords": [] means grounding is not checked for that
# case (no matching textbook in the dataset yet).
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "eval"

CASES = [
    # (id, request, expected)
    ("01", {"grade": "grade_1", "subject": "toan", "lesson": "Các số có hai chữ số",
            "doc_type": "lesson_plan"},
     {"sections": ["objectives", "materials", "activities", "assessment", "appendix"],
      "keywords": ["chữ số", "so sánh"], "activities_total_minutes": [30, 45]}),
    ("02", {"grade": "grade_1", "subject": "toan", "lesson": "Các số có hai chữ số",
            "doc_type": "worksheet", "week": "1"},
     {"sections": ["exercises", "answers"], "keywords": [], "min_answers_chars": 20}),
    ("03", {"grade": "grade_1", "subject": "tieng_viet",
            "lesson": "Ôn các chữ và thanh đã học", "doc_type": "lesson_plan"},
     {"sections": ["objectives", "materials", "activities", "assessment", "appendix"],
      "keywords": ["chữ", "thanh"], "activities_total_minutes": [30, 45]}),
    ("04", {"grade": "grade_2", "subject": "toan",
            "lesson": "Phép cộng không nhớ trong phạm vi 100", "doc_type": "lesson_plan"},
     {"sections": ["objectives", "materials", "activities", "assessment", "appendix"],
      "keywords": ["cộng", "chục"], "activities_total_minutes": [30, 45]}),
    ("05", {"grade": "grade_2", "subject": "toan",
            "lesson": "Phép cộng không nhớ trong phạm vi 100",
            "doc_type": "worksheet", "week": "2"},
     {"sections": ["exercises", "answers"], "keywords": ["cộng"], "min_answers_chars": 20}),
    ("06", {"grade": "grade_3", "subject": "toan", "lesson": "Phép nhân trong phạm vi 5",
            "doc_type": "lesson_plan"},
     {"sections": ["objectives", "materials", "activities", "assessment", "appendix"],
      "keywords": [], "activities_total_minutes": [30, 45]}),
    ("07", {"grade": "grade_2", "subject": "tieng_viet",
            "lesson": "Tập đọc: Cây đa quê hương", "doc_type": "lesson_plan"},
     {"sections": ["objectives", "materials", "activities", "assessment", "appendix"],
      "keywords": [], "activities_total_minutes": [30, 45]}),
    ("08", {"grade": "grade_5", "subject": "ta",
            "lesson": "Greetings and introductions", "doc_type": "lesson_plan"},
     {"sections": ["objectives", "materials", "activities", "assessment", "appendix"],
      "keywords": [], "activities_total_minutes": [30, 45]}),
    ("09", {"grade": "grade_4", "subject": "toan", "lesson": "So sánh hai phân số",
            "doc_type": "lesson_plan"},
     {"sections": ["objectives", "materials", "activities", "assessment", "appendix"],
      "keywords": [], "activities_total_minutes": [30, 45]}),
    ("10", {"grade": "grade_1", "subject": "toan", "lesson": "Số 0 và phép trừ",
            "doc_type": "worksheet", "week": "3"},
     {"sections": ["exercises", "answers"], "keywords": [], "min_answers_chars": 20}),
]


def main() -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    for case_id, request, expected in CASES:
        name = f"case_{case_id}"
        (BASE / f"{name}_request.json").write_text(
            json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
        (BASE / f"{name}_expected.json").write_text(
            json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Seeded {len(CASES)} evaluation cases into {BASE}")


if __name__ == "__main__":
    main()
