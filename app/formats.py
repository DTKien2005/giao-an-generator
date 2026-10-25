"""Format library (plan §2/§3): default templates per document type, plus
extraction of a user's own format from an uploaded lesson plan (plan §3.3)."""
import json
import re

from . import config

_SUBJECT_LABEL = {
    "toan": "Toán", "tieng_viet": "Tiếng Việt", "ta": "Tiếng Anh",
    "khoa_hoc": "Khoa học", "dao_duc": "Đạo đức",
}

_KNOWN_LABELS = [
    "MỤC TIÊU", "ĐỒ DÙNG DẠY HỌC", "CÁC HOẠT ĐỘNG DẠY HỌC", "ĐÁNH GIÁ",
    "PHỤ LỤC", "BÀI TẬP", "ĐÁP ÁN",
]
_SECTION_BY_LABEL = {
    "MỤC TIÊU": "objectives", "ĐỒ DÙNG DẠY HỌC": "materials",
    "CÁC HOẠT ĐỘNG DẠY HỌC": "activities", "ĐÁNH GIÁ": "assessment",
    "PHỤ LỤC": "appendix", "BÀI TẬP": "exercises", "ĐÁP ÁN": "answers",
}


def default_format_spec(doc_type: str) -> dict:
    path = config.DATASET_DIR / "format_templates" / f"{doc_type}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    # Minimal built-in fallback if the template files are missing.
    if doc_type == "worksheet":
        return {"doc_type": "worksheet", "title": "PHIẾU BÀI TẬP",
                "sections": [{"id": "exercises", "type": "exercises", "label": "BÀI TẬP"},
                             {"id": "answers", "type": "text", "label": "ĐÁP ÁN"}]}
    return {"doc_type": "lesson_plan", "title": "GIÁO ÁN",
            "sections": [{"id": "objectives", "type": "bullets", "label": "I. MỤC TIÊU"},
                         {"id": "materials", "type": "bullets", "label": "II. ĐỒ DÙNG DẠY HỌC"},
                         {"id": "activities", "type": "activities", "label": "III. CÁC HOẠT ĐỘNG DẠY HỌC"},
                         {"id": "assessment", "type": "text", "label": "IV. ĐÁNH GIÁ"},
                         {"id": "appendix", "type": "text", "label": "PHỤ LỤC"}]}


def resolve_title(spec: dict, document: dict) -> str:
    """Fill a template title like 'GIÁO ÁN {subject_upper} LỚP {grade_num}'."""
    grade_num = (document.get("grade") or "").replace("grade_", "")
    subject = document.get("subject") or ""
    replacements = {
        "{subject_upper}": _SUBJECT_LABEL.get(subject, subject.upper() if subject else "…"),
        "{grade_num}": grade_num or "…",
        "{week}": str(document.get("week") or "…"),
    }
    title = spec.get("title", "TÀI LIỆU")
    for key, value in replacements.items():
        title = title.replace(key, value)
    return title


def extract_format_spec(text: str) -> dict | None:
    """Plan §3.3: if the upload looks like a lesson plan, turn its structure
    (section headings, order) into a format spec. Returns None when the text
    has no recognizable structure (→ caller falls back to the default template)."""
    headings: list[tuple[str, str]] = []  # (section_id, label as written)
    for line in text.splitlines():
        line_uc = line.strip().upper()
        for label in _KNOWN_LABELS:
            if label in line_uc:
                section_id = _SECTION_BY_LABEL[label]
                if not any(sid == section_id for sid, _ in headings):
                    headings.append((section_id, line.strip()))
                break
    if len(headings) < 2:
        return None

    sections = []
    for section_id, raw_label in headings:
        sec = {"id": section_id, "label": raw_label}
        if section_id == "objectives":
            sec["type"] = "bullets"
        elif section_id == "materials":
            sec["type"] = "bullets"
        elif section_id == "activities":
            sec["type"] = "activities"
        else:
            sec["type"] = "text"
        sections.append(sec)

    first_line = next((l.strip() for l in text.splitlines() if l.strip()), "TÀI LIỆU")
    return {
        "doc_type": "lesson_plan",
        "title": first_line[:80],
        "source": "user_upload",
        "sections": sections,
    }
