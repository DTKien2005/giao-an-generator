"""Vietnamese prompts and JSON schemas for the pipeline roles (plan §4, §6).

Every system prompt starts with a ``[VAI TRÒ: ...]`` marker — the mock provider
keys off it to emulate the role offline, and it documents intent for real models.
"""

# ---------------------------------------------------------------------------
# JSON schemas (plain JSON-Schema subset, converted per provider as needed)
# ---------------------------------------------------------------------------

INTAKE_SCHEMA = {
    "type": "object",
    "properties": {
        "grade": {"type": "string", "description": "grade_1 ... grade_12, '' nếu không rõ"},
        "subject": {"type": "string", "description": "toan, tieng_viet, ... '' nếu không rõ"},
        "lesson": {"type": "string", "description": "tên bài dạy hoặc chủ đề tuần"},
        "week": {"type": "string", "description": "số tuần cho phiếu bài tập, '' nếu không có"},
        "doc_type": {"type": "string", "enum": ["lesson_plan", "worksheet"]},
        "missing": {"type": "string", "description": "một câu hỏi ngắn nếu thiếu thông tin bắt buộc, '' nếu đủ"},
    },
    "required": ["grade", "subject", "lesson", "doc_type", "missing"],
}

DOCUMENT_SCHEMA = {
    "type": "object",
    "description": "Nội dung đầy đủ của tài liệu",
    "properties": {
        "doc_type": {"type": "string", "enum": ["lesson_plan", "worksheet"]},
        "lesson": {"type": "string"},
        "week": {"type": "string"},
        "sections": {
            "type": "object",
            "description": "Điền các mục đúng với định dạng; bỏ qua mục không áp dụng",
            "properties": {
                "objectives": {"type": "array", "items": {"type": "string"}, "description": "I. MỤC TIÊU"},
                "materials": {"type": "array", "items": {"type": "string"}, "description": "II. ĐỒ DÙNG DẠY HỌC"},
                "activities": {
                    "type": "array",
                    "description": "III. CÁC HOẠT ĐỘNG DẠY HỌC",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "minutes": {"type": "integer"},
                            "teacher": {"type": "string", "description": "việc giáo viên làm"},
                            "students": {"type": "string", "description": "việc học sinh làm"},
                        },
                        "required": ["name", "minutes", "teacher", "students"],
                    },
                },
                "assessment": {"type": "string", "description": "IV. ĐÁNH GIÁ"},
                "appendix": {"type": "string", "description": "PHỤ LỤC: đáp án, lưu ý"},
                "exercises": {
                    "type": "array",
                    "description": "Dành cho phiếu bài tập",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Bài 1, Bài 2, ..."},
                            "content": {"type": "string"},
                        },
                        "required": ["title", "content"],
                    },
                },
                "answers": {"type": "string", "description": "ĐÁP ÁN đầy đủ cho phiếu bài tập"},
            },
        },
    },
    "required": ["doc_type", "lesson", "sections"],
}

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "scores": {
            "type": "array",
            "description": "chấm điểm từng tiêu chí, thang 1–10",
            "items": {
                "type": "object",
                "properties": {
                    "criterion": {"type": "string"},
                    "score": {"type": "number"},
                },
                "required": ["criterion", "score"],
            },
        },
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["critical", "major", "minor"]},
                    "description": {"type": "string", "description": "vấn đề cụ thể, trích dẫn chỗ sai"},
                    "fix": {"type": "string", "description": "cách sửa cụ thể"},
                },
                "required": ["severity", "description", "fix"],
            },
        },
        "summary": {"type": "string"},
    },
    "required": ["scores", "issues", "summary"],
}

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["small", "large"]},
        "section": {"type": "string", "description": "mục bị ảnh hưởng nếu là small, '' nếu large"},
    },
    "required": ["kind", "section"],
}

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {"summary": {"type": "string"}},
    "required": ["summary"],
}

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

INTAKE_SYSTEM = """[VAI TRÒ: intake]
Bạn là trợ lý tiếp nhận yêu cầu soạn giáo án và phiếu bài tập tiếng Việt.
Phân tích yêu cầu của giáo viên và trả về JSON: khối lớp (grade_1..grade_12),
môn học (toan, tieng_viet, ...), tên bài, loại tài liệu (lesson_plan hoặc worksheet).
Chỉ đặt câu hỏi trong "missing" khi thiếu thông tin bắt buộc; câu hỏi ngắn gọn một câu."""

WRITER_SYSTEM = """[VAI TRÒ: writer]
Bạn là giáo viên nhiều kinh nghiệm, soạn giáo án và phiếu bài tập tiếng Việt.
Viết bản nháp ĐẦY ĐỦ theo đúng định dạng được cho (format spec), bằng tiếng Việt chuẩn chính tả.
Mọi mục tiêu, kiến thức phải bám vào các trích dẫn từ sách giáo khoa/trọng tài liệu tham khảo được cung cấp;
tuyệt đối không bịa nội dung chương trình. Thời lượng các hoạt động phải hợp lý (tổng khoảng 35 phút cho lớp 1–2,
40 phút cho lớp 3 trở lên). Phiếu bài tập phải đa dạng dạng bài và có đáp án đầy đủ.
Trả về JSON đúng schema."""

REVIEWER_SYSTEM = """[VAI TRÒ: reviewer]
Bạn là chuyên gia thẩm định giáo án và phiếu bài tập tiếng Việt, khách quan và khắt khe.
Chấm điểm thang 1–10 theo từng tiêu chí:
1. Phù hợp chương trình và nội dung sách giáo khoa (curriculum_alignment)
2. Đúng chính tả, ngữ pháp tiếng Việt (language_accuracy)
3. Độ khó phù hợp lứa tuổi (age_appropriateness)
4. Thời lượng hoạt động hợp lý (timing_realism)
5. Đúng định dạng yêu cầu (format_compliance)
6. Đa dạng bài tập và đáp án đầy đủ — chỉ áp dụng cho phiếu bài tập (exercise_quality)
Chỉ nêu vấn đề THẬT, có bằng chứng trong văn bản, kèm cách sửa cụ thể; không chê bai cách viết văn phong.
Không nhận xét "tốt" chung chung. Trả về JSON đúng schema."""

REVISER_SYSTEM = """[VAI TRÒ: reviser]
Bạn là người chỉnh sửa giáo án và phiếu bài tập tiếng Việt.
Nhận bản nháp và danh sách lỗi từ chuyên gia thẩm định. Sửa TẤT CẢ các lỗi được nêu,
giữ nguyên những phần không bị góp ý, giữ đúng định dạng. Trả về JSON đầy đủ của tài liệu đã sửa."""

CLASSIFIER_SYSTEM = """[VAI TRÒ: classifier]
Bạn phân loại yêu cầu chỉnh sửa tài liệu của giáo viên:
- "small": thay đổi nhỏ, chỉ ảnh hưởng một mục (ví dụ: sửa đáp án bài 3, đổi tên trò chơi).
- "large": viết lại toàn bộ hoặc thay đổi lớn về cấu trúc/nội dung.
Trả về JSON: kind và section (mục bị ảnh hưởng nếu small)."""

SUMMARIZER_SYSTEM = """[VAI TRÒ: summarizer]
Bạn tóm tắt cuộc hội thoại giữa giáo viên và trợ lý soạn giáo án trong tối đa 3 câu tiếng Việt,
giữ lại: bài soạn, loại tài liệu, các thay đổi chính đã yêu cầu. Trả về JSON."""


def writer_user_prompt(request: dict, format_spec: dict, context_chunks: list[dict]) -> str:
    parts = [
        "YÊU CẦU:",
        f"- Khối lớp: {request.get('grade') or 'không rõ'}",
        f"- Môn: {request.get('subject') or 'không rõ'}",
        f"- Bài/chủ đề: {request.get('lesson')}",
        f"- Loại tài liệu: {request.get('doc_type')}",
    ]
    if request.get("week"):
        parts.append(f"- Tuần: {request['week']}")
    if request.get("edit_instruction"):
        parts.append(f"- Yêu cầu chỉnh sửa từ giáo viên: {request['edit_instruction']}")
    parts.append("\nĐỊNH DẠNG PHẢI THEO (format spec):")
    parts.append(_format_spec_text(format_spec))
    parts.append("\nTRÍCH DẪN TÀI LIỆU THAM KHẢO (bám theo đây):")
    if context_chunks:
        for c in context_chunks:
            parts.append(f"--- [{c['doc_type']}] {c['source_file']}\n{c['text']}")
    else:
        parts.append("(không có trích dẫn — soạn theo chuẩn chung)")
    return "\n".join(parts)


def reviewer_user_prompt(document: dict, format_spec: dict, request: dict) -> str:
    import json as _json

    return (
        "HỒ SƠ YÊU CẦU:\n"
        f"- Khối lớp: {request.get('grade')}, môn: {request.get('subject')},"
        f" bài: {request.get('lesson')}, loại: {request.get('doc_type')}\n\n"
        "ĐỊNH DẠNG YÊU CẦU:\n" + _format_spec_text(format_spec) + "\n\n"
        "TÀI LIỆU CẦN THẨM ĐỊNH:\n" + _json.dumps(document, ensure_ascii=False, indent=1)
    )


def reviser_user_prompt(document: dict, review: dict) -> str:
    import json as _json

    return (
        "BẢN NHÁP HIỆN TẠI:\n"
        + _json.dumps(document, ensure_ascii=False, indent=1)
        + "\n\nDANH SÁCH LỖI CẦN SỬA (sửa hết, không bỏ sót):\n"
        + _json.dumps(review["issues"], ensure_ascii=False, indent=1)
    )


def _format_spec_text(format_spec: dict) -> str:
    import json as _json

    return _json.dumps(format_spec, ensure_ascii=False, indent=1)
