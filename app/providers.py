"""Multi-model access behind one interface (plan §6):

    generate(messages, json_schema, model, provider) -> dict

Adapters: ``gemini`` (REST v1beta, structured output via responseSchema) and
``mock`` (deterministic, role-aware — keeps the whole pipeline runnable offline
for development and tests). Every call validates the JSON response and retries
once on failure, as the plan requires.
"""
import json
import re

from . import config


class ProviderError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Gemini REST adapter
# ---------------------------------------------------------------------------

def _to_gemini_schema(schema):
    """Convert a plain JSON-Schema subset to Gemini's responseSchema dialect."""
    if not isinstance(schema, dict):
        return schema
    out = {}
    if isinstance(schema.get("type"), str):
        out["type"] = schema["type"].upper()
    if "description" in schema:
        out["description"] = schema["description"]
    if "enum" in schema:
        out["enum"] = schema["enum"]
    if "properties" in schema:
        out["properties"] = {k: _to_gemini_schema(v) for k, v in schema["properties"].items()}
    if "required" in schema:
        out["required"] = schema["required"]
    if "items" in schema:
        out["items"] = _to_gemini_schema(schema["items"])
    return out


def _gemini_call(messages, json_schema, model, temperature):
    import httpx

    system = "\n".join(m["content"] for m in messages if m["role"] == "system")
    contents = [
        {"role": "user" if m["role"] in ("user", "tool") else "model",
         "parts": [{"text": m["content"]}]}
        for m in messages if m["role"] != "system"
    ]
    body: dict = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": config.MAX_TOKENS_PER_CALL,
            "responseMimeType": "application/json",
        },
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if json_schema:
        body["generationConfig"]["responseSchema"] = _to_gemini_schema(json_schema)

    resp = httpx.post(
        f"{config.GEMINI_BASE_URL}/models/{model}:generateContent",
        params={"key": _gemini_key()},
        json=body,
        timeout=180,
    )
    if resp.status_code != 200:
        raise ProviderError(f"Gemini HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    try:
        text = "".join(
            p.get("text", "") for p in data["candidates"][0]["content"]["parts"]
        )
    except (KeyError, IndexError) as exc:
        raise ProviderError(f"Gemini trả về phản hồi không đọc được: {data}") from exc
    return text


def _gemini_key() -> str:
    from . import keys

    key = keys.get_api_key("gemini")
    if not key:
        raise ProviderError("Chưa cấu hình khoá Gemini (GEMINI_API_KEY hoặc Cài đặt)")
    return key


# ---------------------------------------------------------------------------
# OpenAI-compatible adapter (OpenAI, Ollama, LM Studio, vLLM — plan §6)
# ---------------------------------------------------------------------------

def _openai_call(messages, json_schema, model, temperature, base_url: str, api_key: str) -> str:
    import httpx

    payload_messages = []
    system = "\n".join(m["content"] for m in messages if m["role"] == "system")
    if system:
        payload_messages.append({"role": "system", "content": system})
    payload_messages += [
        {"role": "user" if m["role"] in ("user", "tool") else "assistant",
         "content": m["content"]}
        for m in messages if m["role"] != "system"
    ]
    body: dict = {
        "model": model,
        "messages": payload_messages,
        "temperature": temperature,
        "max_tokens": config.MAX_TOKENS_PER_CALL,
    }
    if json_schema:
        body["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    resp = httpx.post(f"{base_url.rstrip('/')}/chat/completions", json=body,
                      headers=headers, timeout=180)
    if resp.status_code != 200:
        raise ProviderError(f"OpenAI-compatible HTTP {resp.status_code}: {resp.text[:300]}")
    try:
        return resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise ProviderError(f"Phản hồi không đọc được: {resp.text[:300]}") from exc


# ---------------------------------------------------------------------------
# Anthropic adapter
# ---------------------------------------------------------------------------

def _anthropic_call(messages, json_schema, model, temperature, base_url: str, api_key: str) -> str:
    import httpx

    if not api_key:
        raise ProviderError("Chưa cấu hình khoá Anthropic")
    system = "\n".join(m["content"] for m in messages if m["role"] == "system")
    body = {
        "model": model,
        "max_tokens": config.MAX_TOKENS_PER_CALL,
        "temperature": temperature,
        "messages": [
            {"role": "user" if m["role"] in ("user", "tool") else "assistant",
             "content": m["content"]}
            for m in messages if m["role"] != "system"
        ],
    }
    if system:
        body["system"] = system + ("\nChỉ trả về JSON hợp lệ." if json_schema else "")
    resp = httpx.post(f"{base_url.rstrip('/')}/v1/messages", json=body,
                      headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                      timeout=180)
    if resp.status_code != 200:
        raise ProviderError(f"Anthropic HTTP {resp.status_code}: {resp.text[:300]}")
    try:
        return "".join(b.get("text", "") for b in resp.json()["content"])
    except (KeyError, IndexError) as exc:
        raise ProviderError(f"Phản hồi không đọc được: {resp.text[:300]}") from exc


# ---------------------------------------------------------------------------
# Mock adapter — deterministic, role-aware, offline
# ---------------------------------------------------------------------------

_ROLE_RE = re.compile(r"\[VAI TRÒ: (\w+)\]")

_SUBJECT_LABEL = {"toan": "Toán", "tieng_viet": "Tiếng Việt", "ta": "Tiếng Anh"}

_GRADE_RE = re.compile(r"(?:lớp|khoi|khối|grade_?)\s*([1-9]|1[0-2])", re.IGNORECASE)
_SUBJECT_RE = re.compile(r"(toán|tiếng việt|tieng viet|tiếng anh)", re.IGNORECASE)


def _extract_context(user_text: str) -> str:
    marker = "TRÍCH DẪN TÀI LIỆU THAM KHẢO"
    if marker in user_text:
        return user_text.split(marker, 1)[1]
    return ""


def _req_field(user_text: str, label: str) -> str:
    m = re.search(rf"{label}:\s*(.+)", user_text)
    return m.group(1).strip() if m else ""


def _mock_intake(user_text: str) -> dict:
    grade_m = _GRADE_RE.search(user_text)
    grade = f"grade_{grade_m.group(1)}" if grade_m else ""
    subj_m = _SUBJECT_RE.search(user_text)
    subject = {"toán": "toan", "tiếng việt": "tieng_viet", "tieng viet": "tieng_viet",
               "tiếng anh": "ta"}.get((subj_m.group(1).lower() if subj_m else ""), "")
    doc_type = "worksheet" if ("phiếu" in user_text and "giáo án" not in user_text) or "worksheet" in user_text else "lesson_plan"
    lesson = _req_field(user_text, "Bài/chủ đề")
    if not lesson:
        m = re.search(r"bài\s+(.+)", user_text, re.IGNORECASE)
        if m:
            lesson = m.group(1).strip().rstrip(".")
    week_m = re.search(r"Tuần:\s*(\S+)", user_text) or re.search(r"tuần\s+(\d+)", user_text, re.IGNORECASE)
    missing = "" if (grade and subject and lesson) else "Bạn cho biết khối lớp, môn học và tên bài cần soạn nhé?"
    return {"grade": grade, "subject": subject, "lesson": lesson,
            "week": week_m.group(1) if week_m else "", "doc_type": doc_type, "missing": missing}


def _mock_writer(user_text: str) -> dict:
    request = {
        "grade": _req_field(user_text, "Khối lớp"),
        "subject": _req_field(user_text, "Môn"),
        "lesson": _req_field(user_text, "Bài/chủ đề"),
        "week": _req_field(user_text, "Tuần"),
        "doc_type": _req_field(user_text, "Loại tài liệu"),
    }
    context = _extract_context(user_text)

    # Ground objectives in the textbook's "Yêu cầu cần đạt" when available.
    objectives = []
    m = re.search(r"Yêu cầu cần đạt\n((?:- .+\n?)+)", context)
    if m:
        objectives = [l[2:].strip() for l in m.group(1).strip().splitlines() if l.startswith("-")]
    if not objectives:
        objectives = [f"Học sinh nắm được kiến thức bài {request['lesson']}.",
                      "Học sinh vận dụng được kiến thức vào bài tập.",
                      "Học sinh yêu thích môn học."]

    if request["doc_type"] == "worksheet":
        exercise_lines = []
        m = re.search(r"Bài tập mẫu\n((?:Bài \d+\..+\n?)+)", context)
        if m:
            exercise_lines = [l.strip() for l in m.group(1).strip().splitlines()]
        exercises = [{"title": f"Bài {i + 1}", "content": line.split(".", 1)[1].strip()}
                     for i, line in enumerate(exercise_lines)]
        if not exercises:
            exercises = [
                {"title": "Bài 1", "content": "Viết các số từ 20 đến 50 theo thứ tự."},
                {"title": "Bài 2", "content": "Điền dấu <, > hoặc = vào chỗ chấm: 34 … 43."},
            ]
        return {
            "doc_type": "worksheet", "lesson": request["lesson"], "week": request["week"],
            "sections": {"exercises": exercises},  # answers deliberately omitted → reviewer finds it
        }

    subject_label = _SUBJECT_LABEL.get(request["subject"], request["subject"] or "…")
    return {
        "doc_type": "lesson_plan", "lesson": request["lesson"], "week": request["week"],
        "sections": {
            "objectives": objectives,
            "materials": ["Giáo viên: bảng phụ, que tính, thẻ số.",
                          "Học sinh: bảng con, phấn, que tính."],
            "activities": [
                {"name": "Khởi động", "minutes": 5,
                 "teacher": f"Giáo viên tổ chức trò chơi ôn bài liên quan đến {request['lesson']}.",
                 "students": "Học sinh tham gia trò chơi, khắc sâu bài cũ."},
                {"name": "Hình thành kiến thức", "minutes": 12,
                 "teacher": f"Giáo viên giới thiệu bài {request['lesson']}, hướng dẫn trên đồ dùng trực quan.",
                 "students": "Học sinh quan sát, thao tác với đồ dùng, trả lời câu hỏi."},
                {"name": "Luyện tập", "minutes": 10,
                 "teacher": "Giáo viên giao bài tập, quan sát và giúp đỡ học sinh.",
                 "students": "Học sinh làm bài vào bảng con, chữa bài chung."},
                {"name": "Vận dụng", "minutes": 5,
                 "teacher": "Giáo viên tổ chức trò chơi củng cố.",
                 "students": "Học sinh chơi và nêu lại kiến thức đã học."},
            ],
            "assessment": "Giáo viên nhận xét tinh thần học tập và mức độ hoàn thành bài tập của học sinh.",
        },  # appendix deliberately omitted → reviewer finds it
    }


def _mock_reviewer(user_text: str) -> dict:
    scores = [
        {"criterion": "curriculum_alignment", "score": 9},
        {"criterion": "language_accuracy", "score": 9},
        {"criterion": "age_appropriateness", "score": 9},
        {"criterion": "timing_realism", "score": 9},
        {"criterion": "format_compliance", "score": 9},
    ]
    issues = []
    document = json.loads(_json_block(user_text.split("TÀI LIỆU CẦN THẨM ĐỊNH:")[1]))
    sections = document.get("sections", {})
    if document.get("doc_type") == "worksheet":
        if not sections.get("answers"):
            issues.append({
                "severity": "major",
                "description": "Phiếu bài tập thiếu mục ĐÁP ÁN.",
                "fix": "Bổ sung mục answers với đáp án đầy đủ cho từng bài.",
            })
        scores.append({"criterion": "exercise_quality",
                       "score": 9 if not issues else 6})
    else:
        if not sections.get("appendix"):
            issues.append({
                "severity": "major",
                "description": "Giáo án thiếu mục PHỤ LỤC (đáp án, lưu ý).",
                "fix": "Bổ sung mục appendix chứa đáp án các bài tập trong giáo án.",
            })
    if issues:
        for s in scores:
            s["score"] = min(s["score"], 8)
    return {"scores": scores, "issues": issues,
            "summary": "Đạt yêu cầu" if not issues else "Cần bổ sung mục còn thiếu."}


_SECTION_KEYWORDS = {
    "objectives": ("mục tiêu",), "materials": ("đồ dùng",),
    "activities": ("hoạt động", "trò chơi"), "assessment": ("đánh giá",),
    "exercises": ("bài tập",), "answers": ("đáp án",), "appendix": ("phụ lục",),
}


def _mock_reviser(user_text: str) -> dict:
    draft = json.loads(_json_block(user_text.split("BẢN NHÁP HIỆN TẠI:")[1].split("DANH SÁCH LỖI CẦN SỬA")[0]))
    issues = json.loads(_json_block(user_text.split("DANH SÁCH LỖI CẦN SỬA")[1]))
    if isinstance(issues, dict):  # single-issue list collapses to a bare object
        issues = [issues]
    sections = draft.setdefault("sections", {})

    for issue in issues:
        fix = str(issue.get("fix", "")).strip()
        # loop convergence: fill the mandatory section the reviewer demands first
        if draft["doc_type"] == "worksheet" and not sections.get("answers"):
            sections["answers"] = "\n".join(
                f"{ex['title']}: hoàn thành theo nội dung bài."
                for ex in sections.get("exercises", [])
            )
            continue
        if draft["doc_type"] == "lesson_plan" and not sections.get("appendix"):
            total = sum(a.get("minutes", 0) for a in sections.get("activities", []))
            sections["appendix"] = (f"Bài tập về nhà: ôn lại bài {draft['lesson']}"
                                    f" (tổng thời lượng trên lớp: {total} phút).")
            continue
        if not fix:
            continue
        # targeted edit: apply the fix to the section it mentions
        target = next((key for key, words in _SECTION_KEYWORDS.items()
                       if any(w in fix.lower() for w in words)), None)
        if target is None:
            target = "answers" if draft["doc_type"] == "worksheet" else "appendix"
        current = sections.get(target)
        if isinstance(current, list):
            sections[target] = current + [f"Chỉnh sửa theo yêu cầu: {fix}"]
        else:
            sections[target] = f"{current}\nChỉnh sửa theo yêu cầu: {fix}" if current \
                else f"Chỉnh sửa theo yêu cầu: {fix}"
    return draft


def _mock_classifier(user_text: str) -> dict:
    big = any(w in user_text for w in ("viết lại", "làm lại", "soạn lại", "thay đổi toàn bộ", "khác"))
    return {"kind": "large" if big else "small", "section": ""}


def _mock_summarizer(user_text: str) -> dict:
    first = user_text.strip().splitlines()[0] if user_text.strip() else ""
    return {"summary": first[:300]}


def _json_block(text: str) -> str:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ProviderError("Mock: không tìm thấy JSON trong văn bản")
    return m.group(0)


def _mock_call(messages, json_schema) -> str:
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user = "\n".join(m["content"] for m in messages if m["role"] != "system")
    role_m = _ROLE_RE.search(system)
    role = role_m.group(1) if role_m else ""
    handlers = {
        "intake": _mock_intake, "writer": _mock_writer, "reviewer": _mock_reviewer,
        "reviser": _mock_reviser, "classifier": _mock_classifier, "summarizer": _mock_summarizer,
    }
    handler = handlers.get(role)
    if handler is None:
        raise ProviderError(f"Mock: chưa hỗ trợ vai trò '{role}'")
    return json.dumps(handler(user), ensure_ascii=False)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return json.loads(text)


def _validate(parsed: dict, json_schema: dict) -> None:
    for field in json_schema.get("required", []):
        if field not in parsed:
            raise ValueError(f"Thiếu trường bắt buộc: {field}")


def generate(messages: list[dict], json_schema: dict | None = None, *,
             model: str | None = None, provider: str | None = None,
             temperature: float = 0.4) -> dict:
    """Run one model call and return parsed JSON. Retries once on invalid JSON (plan §6)."""
    from . import keys

    provider = provider or keys.get_default_provider()
    if provider not in ("gemini", "openai", "anthropic", "local", "mock"):
        raise ProviderError(f"Không biết provider: {provider}")
    last_error: Exception | None = None
    for attempt in range(2):
        attempt_messages = messages
        if attempt == 1:
            attempt_messages = messages + [
                {"role": "user", "content": "Phản hồi trước không đúng JSON. Chỉ trả về JSON hợp lệ đúng schema."},
            ]
        if provider == "gemini":
            text = _gemini_call(attempt_messages, json_schema,
                                model or keys.get_model("writer"), temperature)
        elif provider in ("openai", "local"):
            base_url = keys.get_base_url(provider)
            text = _openai_call(attempt_messages, json_schema,
                                model or keys.get_model("writer"), temperature,
                                base_url, keys.get_api_key(provider))
        elif provider == "anthropic":
            text = _anthropic_call(attempt_messages, json_schema,
                                   model or keys.get_model("writer"), temperature,
                                   keys.get_base_url("anthropic"), keys.get_api_key("anthropic"))
        else:  # mock
            text = _mock_call(attempt_messages, json_schema)
        try:
            parsed = _parse_json(text)
            if json_schema:
                _validate(parsed, json_schema)
            return parsed
        except (ValueError, json.JSONDecodeError) as exc:
            last_error = exc
    raise ProviderError(f"Model trả về JSON không hợp lệ sau 1 lần thử lại: {last_error}")
