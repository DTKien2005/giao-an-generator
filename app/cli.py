"""Phase 1 CLI (plan §9): run the Writer → Reviewer → Reviser loop from the
command line. Usage:

    python -m app.cli "[mô tả yêu cầu]" [--type lesson_plan|worksheet] [--provider mock|gemini]
"""
import argparse
import json
import sys

from . import db
from .pipeline import run_full_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Chạy quy trình soạn tài liệu từ dòng lệnh")
    parser.add_argument("request", help="Mô tả yêu cầu, ví dụ: giáo án toán lớp 1 bài các số có hai chữ số")
    parser.add_argument("--type", choices=["lesson_plan", "worksheet"], default=None)
    parser.add_argument("--provider", default=None)
    parser.add_argument("--grade", default=None)
    parser.add_argument("--subject", default=None)
    parser.add_argument("--lesson", default=None)
    args = parser.parse_args()

    db.init_db()
    request = {k: v for k, v in {
        "grade": args.grade, "subject": args.subject, "lesson": args.lesson,
        "doc_type": args.type,
    }.items() if v}

    def progress(label: str) -> None:
        print(f"  • {label}", flush=True)

    print(f"Yêu cầu: {args.request}")
    try:
        result = run_full_pipeline(request, args.request, progress=progress, provider=args.provider)
    except Exception as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 1

    print(f"\nHoàn tất — tài liệu #{result['document_id']}, bản ghi phiên bản #{result['version_id']}")
    print(f"Điểm thẩm định trung bình: {result['avg_score']}")
    print(f"Nhận xét: {result['review_summary']}")
    print("\n--- NỘI DUNG ---")
    print(json.dumps(result["document"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
