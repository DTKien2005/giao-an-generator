"""FastAPI web app (plan §8: Python + FastAPI, HTML frontend, jobs table).

Endpoints
- GET  /                     → single-page UI
- POST /api/generate         → start a run (JSON or multipart with an upload)
- GET  /api/runs/{id}/events → Server-Sent Events progress stream (plan §5)
- GET  /api/runs/{id}        → run status/result
- GET  /api/conversations    → history list
- GET  /api/documents/{id}   → document + versions
- GET  /api/versions/{id}/download?fmt=docx|pdf
"""
import json
import queue
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import auth, config, db, keys
from .diffing import diff_documents
from .formats import default_format_spec, extract_format_spec
from .ingest import file_to_text
from .pipeline import MissingInfoError, PipelineError, run_edit, run_full_pipeline, save_version


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Soạn Giáo Án & Phiếu Bài Tập", lifespan=lifespan)

_STATIC = Path(__file__).resolve().parent.parent / "static"
_TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

# ---------------------------------------------------------------------------
# Auth: progressive — open mode until the first account exists (plan §9-P6)
# ---------------------------------------------------------------------------
COOKIE_NAME = "ga_session"


def _session_token(request: Request) -> str | None:
    return request.cookies.get(COOKIE_NAME)


def current_user(request: Request):
    """The logged-in user, the shared sentinel in open mode, or None."""
    return auth.session_user(_session_token(request)) or (
        db.get_conn().execute("SELECT id, name FROM users WHERE id = 1").fetchone()
        if not auth.auth_enabled() else None
    )


@app.middleware("http")
async def auth_guard(request: Request, call_next):
    path = request.url.path
    public = path in ("/", "/api/setup", "/api/login", "/api/me") or path.startswith("/static")
    if not public and path.startswith("/api/") and auth.auth_enabled():
        if auth.session_user(_session_token(request)) is None:
            return JSONResponse({"detail": "Cần đăng nhập"}, status_code=401)
    return await call_next(request)


@app.get("/api/me")
def me(request: Request):
    user = auth.session_user(_session_token(request))
    return {"name": user["name"] if user else None,
            "auth_enabled": auth.auth_enabled()}


@app.post("/api/setup")
async def setup(payload: dict):
    try:
        auth.setup_first_user(str(payload.get("name", "")), str(payload.get("password", "")))
    except (PermissionError, ValueError) as exc:
        raise HTTPException(400 if isinstance(exc, ValueError) else 409, str(exc))
    token = auth.login(str(payload["name"]), str(payload["password"]))
    response = JSONResponse({"ok": True, "name": payload["name"]})
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax", max_age=7 * 24 * 3600)
    return response


@app.post("/api/login")
async def login(payload: dict):
    token = auth.login(str(payload.get("name", "")), str(payload.get("password", "")))
    if not token:
        raise HTTPException(401, "Sai tên đăng nhập hoặc mật khẩu")
    response = JSONResponse({"ok": True})
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax", max_age=7 * 24 * 3600)
    return response


@app.post("/api/logout")
async def logout(request: Request):
    token = _session_token(request)
    if token:
        auth.logout(token)
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE_NAME)
    return response


@app.post("/api/users")
async def add_user(payload: dict, request: Request):
    if not auth.auth_enabled():
        raise HTTPException(400, "Chưa bật đăng nhập — dùng /api/setup trước")
    if auth.session_user(_session_token(request)) is None:
        raise HTTPException(401, "Cần đăng nhập để tạo người dùng mới")
    try:
        user_id = auth.create_user(str(payload.get("name", "")), str(payload.get("password", "")))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"id": user_id}

# run_id → {"subs": [queue…], "done": bool, "result": …, "error": …}
_live_runs: dict[int, dict] = {}
_lock = threading.Lock()


def _publish(run_id: int, payload: dict) -> None:
    with _lock:
        entry = _live_runs.setdefault(run_id, {"subs": [], "done": False, "result": None, "error": None})
        for q in entry["subs"]:
            q.put_nowait(payload)


def _finish(run_id: int, result: dict | None, error: str | None) -> None:
    _publish(run_id, {"type": "done" if result else "error",
                      **({"result": result} if result else {"error": error})})
    with _lock:
        entry = _live_runs[run_id]
        entry["done"], entry["result"], entry["error"] = True, result, error


def _worker(run_id: int, job) -> None:
    def progress(label: str) -> None:
        _publish(run_id, {"type": "progress", "label": label})
        db.get_conn().execute("UPDATE runs SET progress = ? WHERE id = ?", (label, run_id))
        db.get_conn().commit()

    try:
        result = job(run_id, progress)
        db.get_conn().execute(
            "UPDATE runs SET status = 'done', result_version_id = ? WHERE id = ?",
            (result["version_id"], run_id))
        db.get_conn().commit()
        _finish(run_id, result, None)
    except MissingInfoError as exc:
        db.get_conn().execute("UPDATE runs SET status = 'error', error = ? WHERE id = ?",
                              (exc.question, run_id))
        db.get_conn().commit()
        _finish(run_id, None, f"CẦN THÊM THÔNG TIN: {exc.question}")
    except Exception as exc:  # noqa: BLE001 — surface every failure to the UI
        db.get_conn().execute("UPDATE runs SET status = 'error', error = ? WHERE id = ?",
                              (str(exc), run_id))
        db.get_conn().commit()
        _finish(run_id, None, f"LỖI: {exc}")


def _start_run(kind: str, job) -> int:
    conn = db.get_conn()
    cur = conn.execute(
        "INSERT INTO runs (kind, status) VALUES (?, 'queued')", (kind,))
    run_id = cur.lastrowid
    conn.execute("INSERT INTO jobs (run_id) VALUES (?)", (run_id,))
    conn.commit()
    with _lock:
        _live_runs[run_id] = {"subs": [], "done": False, "result": None, "error": None}
    threading.Thread(target=_worker, args=(run_id, job), daemon=True).start()
    return run_id


def _extract_upload(upload: UploadFile) -> str:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in (".docx", ".pdf", ".txt", ".md"):
        raise HTTPException(400, f"Chưa hỗ trợ tệp {suffix or '(không rõ)'} — dùng .docx, .pdf, .txt")
    dest = config.UPLOADS_DIR / f"{upload.filename}"
    dest.write_bytes(upload.file.read())
    try:
        if suffix == ".pdf":
            from .ocr import extract_pdf_text

            text, warnings = extract_pdf_text(dest)
            if not text.strip() and warnings:
                raise HTTPException(
                    400, "Tệp PDF là bản quét và chưa có khoá Gemini để OCR: "
                    + "; ".join(warnings[:3]))
            return text
        return file_to_text(dest)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, f"Không đọc được tệp: {exc}") from exc


def _cache_user_spec(user_id: int, doc_type: str, spec: dict) -> None:
    """Plan §3.4: remember the user's extracted format so they need not re-upload."""
    db.get_conn().execute(
        "INSERT INTO settings (key, value) VALUES (?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (f"format_spec:user:{user_id}:{doc_type}", json.dumps(spec, ensure_ascii=False)),
    )
    db.get_conn().commit()


def _cached_user_spec(user_id: int, doc_type: str) -> dict | None:
    row = db.get_conn().execute(
        "SELECT value FROM settings WHERE key = ?",
        (f"format_spec:user:{user_id}:{doc_type}",),
    ).fetchone()
    return json.loads(row["value"]) if row else None


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (_TEMPLATES / "index.html").read_text(encoding="utf-8")


def _own_document(document_id: int, user):
    """A document visible to this user, or 404 (also hides other users' data)."""
    conn = db.get_conn()
    row = conn.execute(
        "SELECT d.* FROM documents d JOIN conversations c ON c.id = d.conversation_id"
        " WHERE d.id = ? AND c.user_id = ?",
        (document_id, user["id"]),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Không tìm thấy tài liệu")
    return row


@app.post("/api/generate")
async def generate(
    request: Request,
    text: str = Form(""),
    grade: str = Form(""),
    subject: str = Form(""),
    lesson: str = Form(""),
    week: str = Form(""),
    doc_type: str = Form(""),
    file: UploadFile | None = File(None),
):
    user = current_user(request)
    if user is None:
        raise HTTPException(401, "Cần đăng nhập")
    _check_rate_limit(request)
    source_text = text or ""
    user_spec = None
    if file is not None and file.filename:
        uploaded_text = _extract_upload(file)
        source_text = uploaded_text + "\n\n" + source_text
        # Plan §3.3: an upload that looks like a lesson plan becomes the
        # user's own format spec and takes priority over the default template.
        user_spec = extract_format_spec(uploaded_text)
        if user_spec and not doc_type:
            doc_type = "lesson_plan"
    if not source_text.strip() and not lesson.strip():
        raise HTTPException(400, "Hãy dán nội dung, tải tệp lên, hoặc ghi tên bài cần soạn.")
    request = {k: v for k, v in {
        "grade": grade, "subject": subject, "lesson": lesson,
        "week": week, "doc_type": doc_type,
    }.items() if v}
    if user_spec:
        request["format_spec"] = user_spec
        _cache_user_spec(1, request.get("doc_type", "lesson_plan"), user_spec)
    else:
        cached = _cached_user_spec(1, request.get("doc_type") or "lesson_plan")
        if cached:
            request["format_spec"] = cached

    def job(run_id: int, progress):
        return run_full_pipeline(request, source_text, progress=progress,
                                 run_id=run_id, user_id=user["id"])

    run_id = _start_run("full", job)
    return {"run_id": run_id}


@app.post("/api/documents/{document_id}/edit")
async def edit_document(document_id: int, instruction: str = Form(...), request: Request = None):
    user = current_user(request)
    if user is None:
        raise HTTPException(401, "Cần đăng nhập")
    _check_rate_limit(request)
    instruction = instruction.strip()
    if not instruction:
        raise HTTPException(400, "Hãy ghi yêu cầu chỉnh sửa.")
    _own_document(document_id, user)

    def job(run_id: int, progress):
        return run_edit(document_id, instruction, progress=progress, run_id=run_id)

    run_id = _start_run("edit", job)
    return {"run_id": run_id}


@app.post("/api/versions/{version_id}/restore")
async def restore_version(version_id: int, request: Request = None):
    """Non-destructive rollback (plan §5): an old version's content is saved as
    a NEW version — the audit trail and diffs stay intact."""
    user = current_user(request)
    if user is None:
        raise HTTPException(401, "Cần đăng nhập")
    version = _own_version(version_id, user)

    def job(run_id: int, progress):
        _publish(run_id, {"type": "progress", "label": "Phục hồi phiên bản…"})
        document = json.loads(version["content"])
        conn = db.get_conn()
        spec_json = conn.execute(
            "SELECT format_spec FROM documents WHERE id = ?",
            (version["document_id"],)).fetchone()["format_spec"]
        format_spec = json.loads(spec_json) if spec_json else \
            default_format_spec(document.get("doc_type", "lesson_plan"))
        new_version_id = save_version(
            version["document_id"], document, format_spec,
            f"Phục hồi từ v{version['version']}")
        conn.execute(
            "UPDATE runs SET document_id = ? WHERE id = ?", (version["document_id"], run_id))
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES"
            " ((SELECT conversation_id FROM documents WHERE id = ?), 'assistant', ?)",
            (version["document_id"], f"Đã phục hồi nội dung phiên bản v{version['version']}."))
        conn.commit()
        _publish(run_id, {"type": "progress", "label": "Kết xuất tệp Word và PDF…"})
        return {"conversation_id": None, "document_id": version["document_id"],
                "version_id": new_version_id, "document": document,
                "review_summary": f"Đã phục hồi từ v{version['version']}", "kind": "restore"}

    run_id = _start_run("restore", job)
    return {"run_id": run_id}


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, request: Request = None):
    """Soft delete: hidden from the list, data and files kept."""
    user = current_user(request)
    if user is None:
        raise HTTPException(401, "Cần đăng nhập")
    conn = db.get_conn()
    row = conn.execute(
        "SELECT id FROM conversations WHERE id = ? AND user_id = ? AND deleted_at IS NULL",
        (conversation_id, user["id"])).fetchone()
    if not row:
        raise HTTPException(404, "Không tìm thấy cuộc trò chuyện")
    conn.execute("UPDATE conversations SET deleted_at = datetime('now') WHERE id = ?",
                 (conversation_id,))
    conn.commit()
    return {"ok": True}


@app.get("/api/documents/{document_id}/diff")
def document_diff(document_id: int, from_version: int, to_version: int, request: Request = None):
    user = current_user(request)
    if user is None:
        raise HTTPException(401, "Cần đăng nhập")
    _own_document(document_id, user)
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT version, content FROM document_versions"
        " WHERE document_id = ? AND version IN (?, ?)",
        (document_id, from_version, to_version),
    ).fetchall()
    if len(rows) != 2:
        raise HTTPException(404, "Không tìm thấy hai phiên bản để so sánh")
    by_version = {r["version"]: json.loads(r["content"]) for r in rows}
    return diff_documents(by_version[from_version], by_version[to_version])


@app.get("/api/runs/{run_id}/events")
def run_events(run_id: int):
    q: queue.Queue = queue.Queue()
    with _lock:
        entry = _live_runs.get(run_id)
        if entry is None:
            raise HTTPException(404, "Không tìm thấy run đang chạy")
        entry["subs"].append(q)
        already_done, result, error = entry["done"], entry["result"], entry["error"]

    def stream():
        if already_done:
            yield f"data: {json.dumps({'type': 'done' if result else 'error', 'result': result, 'error': error}, ensure_ascii=False)}\n\n"
            return
        while True:
            try:
                payload = q.get(timeout=120)
            except queue.Empty:
                yield ": keep-alive\n\n"
                continue
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            if payload.get("type") in ("done", "error"):
                break

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


@app.get("/api/runs/{run_id}")
def run_status(run_id: int):
    row = db.get_conn().execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Không tìm thấy run")
    return dict(row)


@app.get("/api/conversations")
def conversations(request: Request = None):
    user = current_user(request)
    if user is None:
        raise HTTPException(401, "Cần đăng nhập")
    rows = db.get_conn().execute(
        "SELECT c.id, c.title, c.updated_at,"
        " (SELECT COUNT(*) FROM documents d WHERE d.conversation_id = c.id) AS documents"
        " FROM conversations c WHERE c.user_id = ? AND c.deleted_at IS NULL"
        " ORDER BY c.updated_at DESC LIMIT 100",
        (user["id"],),
    ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/conversations/{conversation_id}/documents")
def conversation_documents(conversation_id: int, request: Request = None):
    user = current_user(request)
    if user is None:
        raise HTTPException(401, "Cần đăng nhập")
    rows = db.get_conn().execute(
        "SELECT d.id, d.title, d.doc_type, d.grade, d.subject FROM documents d"
        " JOIN conversations c ON c.id = d.conversation_id"
        " WHERE d.conversation_id = ? AND c.user_id = ? ORDER BY d.id DESC",
        (conversation_id, user["id"]),
    ).fetchall()
    return [dict(r) for r in rows]


def _own_version(version_id: int, user):
    conn = db.get_conn()
    row = conn.execute(
        "SELECT v.* FROM document_versions v"
        " JOIN documents d ON d.id = v.document_id"
        " JOIN conversations c ON c.id = d.conversation_id"
        " WHERE v.id = ? AND c.user_id = ?",
        (version_id, user["id"]),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Không tìm thấy phiên bản")
    return row


@app.get("/api/versions/{version_id}/preview")
def version_preview(version_id: int, request: Request = None):
    user = current_user(request)
    if user is None:
        raise HTTPException(401, "Cần đăng nhập")
    row = _own_version(version_id, user)
    return json.loads(row["content"])


@app.get("/api/documents/{document_id}")
def document_detail(document_id: int, request: Request = None):
    user = current_user(request)
    if user is None:
        raise HTTPException(401, "Cần đăng nhập")
    doc = _own_document(document_id, user)
    conn = db.get_conn()
    if not doc:
        raise HTTPException(404, "Không tìm thấy tài liệu")
    versions = conn.execute(
        "SELECT id, version, note, file_docx, file_pdf, created_at"
        " FROM document_versions WHERE document_id = ? ORDER BY version DESC",
        (document_id,),
    ).fetchall()
    messages = conn.execute(
        "SELECT role, content, created_at FROM messages WHERE conversation_id = ?"
        " ORDER BY id ASC LIMIT 200",
        (doc["conversation_id"],),
    ).fetchall()
    return {"document": dict(doc), "versions": [dict(v) for v in versions],
            "messages": [dict(m) for m in messages]}


@app.get("/api/versions/{version_id}/download")
def download(version_id: int, fmt: str = "docx", request: Request = None):
    user = current_user(request)
    if user is None:
        raise HTTPException(401, "Cần đăng nhập")
    row = _own_version(version_id, user)
    path = row["file_docx"] if fmt == "docx" else row["file_pdf"]
    if not path or not Path(path).exists():
        raise HTTPException(404, f"Chưa có tệp {fmt.upper()} cho phiên bản này")
    ext = "docx" if fmt == "docx" else "pdf"
    filename = Path(path).name
    return FileResponse(path, filename=filename,
                        media_type={"docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    "pdf": "application/pdf"}[ext])


# ---------------------------------------------------------------------------
# Settings (plan §6) + light rate limiting (plan §9 Phase 6)
# ---------------------------------------------------------------------------

RATE_LIMIT_RUNS = config.RATE_LIMIT_RUNS    # pipeline runs per window (cost cap, plan §10)
RATE_LIMIT_WINDOW = config.RATE_LIMIT_WINDOW
_run_times: dict[str, deque] = defaultdict(deque)


def _check_rate_limit(request: Request) -> None:
    client = request.client.host if request.client else "local"
    now = time.time()
    bucket = _run_times[client]
    while bucket and now - bucket[0] > RATE_LIMIT_WINDOW:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT_RUNS:
        raise HTTPException(
            429, "Đã đạt giới hạn số lần chạy trong 10 phút (giới hạn chi phí). Thử lại sau.")
    bucket.append(now)


@app.get("/api/settings")
def get_settings():
    return keys.settings_summary()


@app.post("/api/settings")
async def update_settings(payload: dict):
    try:
        if "default_provider" in payload:
            keys.set_default_provider(payload["default_provider"])
        for role, model in (payload.get("models") or {}).items():
            if str(model).strip():
                keys.set_model(role, str(model).strip())
        for provider, key in (payload.get("api_keys") or {}).items():
            keys.set_api_key(provider, str(key).strip())  # '' clears the stored key
        for provider, url in (payload.get("base_urls") or {}).items():
            if str(url).strip():
                keys.set_base_url(provider, str(url).strip())
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return keys.settings_summary()
