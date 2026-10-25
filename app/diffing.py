"""Version diffs (plan §5: "view diffs and roll back").

Flattens a document's sections to ordered lines, then diffs section-by-section
with difflib so the UI can highlight what an edit round actually changed.
"""
import difflib

_SECTION_ORDER = ["objectives", "materials", "activities", "assessment",
                  "exercises", "answers", "appendix"]
_SECTION_LABEL = {
    "objectives": "I. Mục tiêu", "materials": "II. Đồ dùng dạy học",
    "activities": "III. Các hoạt động dạy học", "assessment": "IV. Đánh giá",
    "exercises": "Bài tập", "answers": "Đáp án", "appendix": "Phụ lục",
}


def flatten(document: dict) -> dict[str, list[str]]:
    """Document → {section_id: [lines]} for stable, readable diffing."""
    sections = document.get("sections", {})
    flat: dict[str, list[str]] = {}
    for key in _SECTION_ORDER:
        content = sections.get(key)
        if content in (None, "", [], {}):
            continue
        if isinstance(content, list):
            lines = []
            for item in content:
                if isinstance(item, dict):  # activities / exercises
                    if "teacher" in item or "students" in item:
                        lines.append(f"{item.get('name', '')} ({item.get('minutes', '')} phút)")
                        lines.append(f"  GV: {item.get('teacher', '')}")
                        lines.append(f"  HS: {item.get('students', '')}")
                    else:
                        lines.append(f"{item.get('title', '')}: {item.get('content', '')}")
                else:
                    lines.append(str(item))
            flat[key] = lines
        else:
            flat[key] = [line for line in str(content).splitlines() if line.strip()]
    return flat


def diff_documents(old: dict, new: dict) -> list[dict]:
    """Per-section line diff: [{section, label, lines: [{op, text}]}]."""
    old_flat, new_flat = flatten(old), flatten(new)
    result = []
    for key in _SECTION_ORDER:
        if key not in old_flat and key not in new_flat:
            continue
        old_lines, new_lines = old_flat.get(key, []), new_flat.get(key, [])
        if old_lines == new_lines:
            continue
        sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
        lines = []
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            for line in old_lines[i1:i2]:
                lines.append({"op": "removed", "text": line})
            for line in new_lines[j1:j2]:
                lines.append({"op": "added", "text": line})
        result.append({"section": key, "label": _SECTION_LABEL.get(key, key), "lines": lines})
    return result
