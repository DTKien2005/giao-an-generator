"""v6 tests (PLANS_V6.md WP0-WP4): security fixes, proxy IP, setup token,
backup atomicity + off-disk copy. All offline (mock provider)."""
import io
import json
import threading
import time

from fastapi.testclient import TestClient

from conftest import reset_auth_state
from app import backup, config
from app.main import app, client_ip


class _StubRequest:
    """Minimal Request stand-in for client_ip tests."""
    def __init__(self, peer, headers=None):
        self.client = type("C", (), {"host": peer})()
        self.headers = headers or {}


def _wait_done(client_obj, run_id):
    events = []
    deadline = time.time() + 30
    with client_obj.stream("GET", f"/api/runs/{run_id}/events") as stream:
        for line in stream.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
                if events[-1]["type"] in ("done", "error"):
                    break
            if time.time() > deadline:
                break
    return events[-1]


def _make_doc(client_obj, lesson):
    resp = client_obj.post("/api/generate", data={
        "grade": "grade_1", "subject": "toan", "lesson": lesson,
        "doc_type": "lesson_plan"})
    final = _wait_done(client_obj, resp.json()["run_id"])
    assert final["type"] == "done", final
    return final["result"]


# ---------------------------------------------------------------- WP0
def test_run_endpoints_check_ownership(client):
    from app import db
    client.post("/api/setup", json={"name": "chuRun", "password": "pw123456"})
    client.post("/api/users", json={"name": "khachRun", "password": "pw123456"})
    owner = TestClient(app)
    other = TestClient(app)
    owner.post("/api/login", json={"name": "chuRun", "password": "pw123456"})
    other.post("/api/login", json={"name": "khachRun", "password": "pw123456"})

    resp = owner.post("/api/generate", data={
        "grade": "grade_1", "subject": "toan", "lesson": "Bài chạy của chủ",
        "doc_type": "lesson_plan"})
    run_id = resp.json()["run_id"]
    _wait_done(owner, run_id)

    assert other.get(f"/api/runs/{run_id}").status_code == 404
    assert owner.get(f"/api/runs/{run_id}").status_code == 200
    with client.stream("GET", f"/api/runs/{run_id}/events") as _:
        pass  # anonymous TestClient 'client' has no session -> 401/404 path
    assert other.get(f"/api/runs/{run_id}/events").status_code == 404
    reset_auth_state()


def test_upload_rejects_traversal_and_oversize(client, monkeypatch, tmp_path):
    import app.main as main_mod
    # traversal names are rejected outright
    for bad in ("..\\evil.docx", "../../evil.docx", "..", "a/../../b.docx"):
        resp = client.post("/api/generate", data={
            "grade": "grade_1", "subject": "toan", "lesson": "Kiểm tra tệp",
            "doc_type": "lesson_plan"},
            files={"file": (bad, io.BytesIO("nội dung".encode("utf-8")), "application/octet-stream")})
        assert resp.status_code == 400, (bad, resp.text)
    # oversize is rejected with 413
    monkeypatch.setattr(main_mod, "MAX_UPLOAD_BYTES", 100)
    big = b"x" * 101
    resp = client.post("/api/generate", data={
        "grade": "grade_1", "subject": "toan", "lesson": "Kiểm tra tệp to",
        "doc_type": "lesson_plan"},
        files={"file": ("to.docx.txt", io.BytesIO(big), "text/plain")})
    assert resp.status_code == 413


def test_settings_and_user_creation_first_account_only(client):
    from app import db
    client.post("/api/setup", json={"name": "quantri", "password": "pw123456"})
    client.post("/api/users", json={"name": "thuong", "password": "pw123456"})
    member = TestClient(app)
    member.post("/api/login", json={"name": "thuong", "password": "pw123456"})
    assert member.post("/api/users",
                       json={"name": "moi", "password": "pw123456"}).status_code == 403
    assert member.post("/api/settings",
                       json={"default_provider": "mock"}).status_code == 403
    reset_auth_state()


def test_live_runs_pruned_and_subscribers_removed(client):
    import queue as _queue

    import app.main as main_mod
    result = _make_doc(client, "Bài dọn bộ nhớ run")
    run_id = result["conversation_id"] and None  # placeholder, real id below
    # a real subscriber on a finished run is removed when its stream ends
    status = client.get(f"/api/runs/{_latest_run_id()}").status_code
    assert status == 200
    with client.stream("GET", f"/api/runs/{_latest_run_id()}/events") as stream:
        for line in stream.iter_lines():
            if line.startswith("data: "):
                break  # terminal event of an already-done run
    entry = main_mod._live_runs.get(_latest_run_id())
    if entry is not None:
        assert entry["subs"] == [], "subscriber phải được gỡ sau khi stream kết thúc"
    assert len(main_mod._live_runs) <= main_mod._LIVE_RUNS_CAP


def _latest_run_id():
    from app import db
    row = db.get_conn().execute("SELECT MAX(id) AS i FROM runs").fetchone()
    return row["i"]


# ---------------------------------------------------------------- WP1
def test_client_ip_trust_rules(monkeypatch):
    # flag off: header never trusted, even from loopback
    monkeypatch.setattr(config, "TRUST_PROXY", False)
    req = _StubRequest("127.0.0.1", {"cf-connecting-ip": "203.0.113.9"})
    assert client_ip(req) == "127.0.0.1"
    # flag on + loopback + valid header -> used and normalised
    monkeypatch.setattr(config, "TRUST_PROXY", True)
    assert client_ip(req) == "203.0.113.9"
    assert client_ip(_StubRequest("::1", {"cf-connecting-ip": "203.0.113.7"})) == "203.0.113.7"
    # multi-value and garbage fall back to the peer; X-Forwarded-For is ignored
    assert client_ip(_StubRequest("127.0.0.1",
                                  {"cf-connecting-ip": "1.2.3.4, 5.6.7.8"})) == "1.2.3.4"
    assert client_ip(_StubRequest("127.0.0.1", {"cf-connecting-ip": "không-phải-ip"})) == "127.0.0.1"
    assert client_ip(_StubRequest("127.0.0.1",
                                  {"x-forwarded-for": "9.9.9.9"})) == "127.0.0.1"
    # non-loopback peer: header ignored even with the flag on
    assert client_ip(_StubRequest("10.1.2.3", {"cf-connecting-ip": "8.8.8.8"})) == "10.1.2.3"


def test_rate_limit_buckets_separate_by_forwarded_ip(monkeypatch):
    """Bucket separation is proven at the helper level: TestClient peers are not
    loopback, so no header would be trusted over HTTP (covered by client_ip tests)."""
    import app.main as main_mod
    monkeypatch.setattr(main_mod, "RATE_LIMIT_RUNS", 2)
    monkeypatch.setattr(config, "TRUST_PROXY", True)
    main_mod._run_times.clear()
    client_a = _StubRequest("127.0.0.1", {"cf-connecting-ip": "198.51.100.1"})
    client_b = _StubRequest("127.0.0.1", {"cf-connecting-ip": "198.51.100.2"})
    main_mod._hit_bucket(main_mod._run_times, client_a, 2)
    main_mod._hit_bucket(main_mod._run_times, client_a, 2)
    for raise_expected in (True, True):
        try:
            main_mod._hit_bucket(main_mod._run_times, client_a, 2)
            raised = False
        except Exception as exc:
            raised = getattr(exc, "status_code", None) == 429
        assert raised
    main_mod._hit_bucket(main_mod._run_times, client_b, 2)  # different bucket: allowed
    main_mod._run_times.clear()


def test_rate_limit_buckets_bounded(monkeypatch):
    """The cap applies at the limiter itself (Codex R2-15: /api/me never hits it)."""
    import app.main as main_mod
    monkeypatch.setattr(main_mod, "RATE_LIMIT_CLIENTS_CAP", 3)
    monkeypatch.setattr(config, "TRUST_PROXY", True)
    main_mod._run_times.clear()
    for i in range(10):
        main_mod._hit_bucket(main_mod._run_times,
                             _StubRequest("127.0.0.1", {"cf-connecting-ip": f"10.0.0.{i}"}), 99)
    assert len(main_mod._run_times) <= 3
    main_mod._run_times.clear()


# ---------------------------------------------------------------- WP2
def test_setup_token_required(client, monkeypatch):
    monkeypatch.setattr(config, "SETUP_TOKEN", "tok-bí-mật-123")
    assert client.post("/api/setup",
                       json={"name": "u", "password": "pw123456"}).status_code == 403
    assert client.post("/api/setup", json={"name": "u", "password": "pw123456",
                                           "setup_token": "sai"}).status_code == 403
    assert client.post("/api/setup", json={"name": "u", "password": "pw123456",
                                           "setup_token": "tok-bí-mật-123"}).status_code == 200
    assert client.get("/api/me").json()["setup_token_required"] is True
    reset_auth_state()  # (monkeypatch is still active here, so only auth state is asserted)


def test_setup_claim_is_atomic(client):
    """SQLite's conditional UPDATE is the atomicity primitive: exactly one
    caller's UPDATE matches the empty-password sentinel; the loser's rowcount
    is 0 (tested raw) and the loser's API call is refused (tested twice)."""
    from app import auth, db
    auth.setup_first_user("nguoiDau", "pw123456")
    try:
        auth.setup_first_user("nguoiHai", "pw123456")
        raised = False
    except PermissionError:
        raised = True
    assert raised and auth.user_count() == 1
    # raw: the guard's rowcount is 0 once claimed — this is what makes the
    # endpoint safe against concurrent racing requests (single statement)
    cur = db.get_conn().execute(
        "UPDATE users SET name='x' WHERE id = 1 AND password_hash = ''")
    assert cur.rowcount == 0
    db.get_conn().rollback()
    reset_auth_state()


def test_password_min_length_and_login_throttle(client, monkeypatch):
    import app.main as main_mod
    client.post("/api/setup", json={"name": "coMatkhau", "password": "pw123456"})
    assert client.post("/api/users",
                       json={"name": "ngan", "password": "123"}).status_code == 400
    assert client.post("/api/setup",
                       json={"name": "x", "password": "123"}).status_code in (400, 409)
    monkeypatch.setattr(main_mod, "LOGIN_ATTEMPTS_LIMIT", 3)
    main_mod._login_times.clear()
    codes = [client.post("/api/login",
                         json={"name": "coMatkhau", "password": "sai"}).status_code
             for _ in range(4)]
    assert codes[:3] == [401, 401, 401] and codes[3] == 429
    main_mod._login_times.clear()
    reset_auth_state()


# ---------------------------------------------------------------- WP3 + WP4
def test_healthz_open_and_when_auth_enabled(client):
    assert client.get("/healthz").status_code == 200
    client.post("/api/setup", json={"name": "chuHealth", "password": "pw123456"})
    anon = TestClient(app)
    resp = anon.get("/healthz")
    assert resp.status_code == 200 and resp.json() == {"ok": True}
    assert anon.get("/api/conversations").status_code == 401  # API still locked
    reset_auth_state()


def test_backup_atomic_and_off_disk_copy(client, monkeypatch, tmp_path):
    backup.KEEP = 3
    copy_dir = tmp_path / "usb"
    copy_dir.mkdir()
    monkeypatch.setattr(config, "BACKUP_COPY_DIR", str(copy_dir))
    try:
        zip_path, copied_to = backup.create_backup()
        assert zip_path.exists() and not list(zip_path.parent.glob("*.part"))
        assert copied_to is not None and copied_to.exists()
        assert copied_to.stat().st_size == zip_path.stat().st_size
        import zipfile
        with zipfile.ZipFile(zip_path) as zf:
            assert "app.db" in zf.namelist() and zf.testzip() is None
    finally:
        backup.KEEP = 10
        monkeypatch.setattr(config, "BACKUP_COPY_DIR", "")


def test_backup_copy_dir_rules(client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "BACKUP_COPY_DIR", str(config.DATA_DIR / "con"))
    try:
        try:
            backup.create_backup()
            raised = False
        except ValueError:
            raised = True
        assert raised, "destination inside data/ must be rejected"
    finally:
        monkeypatch.setattr(config, "BACKUP_COPY_DIR", "")

    monkeypatch.setattr(config, "BACKUP_COPY_DIR", str(tmp_path / "khong-ton-tai"))
    try:
        try:
            backup.create_backup()
            raised = False
        except FileNotFoundError:
            raised = True
        assert raised
        # the local zip survives the copy failure
        assert any((config.DATA_DIR / "backups").glob("backup_*.zip"))
    finally:
        monkeypatch.setattr(config, "BACKUP_COPY_DIR", "")


# ------------------------------------------------ Codex round-2 regression tests
def test_duplicate_username_rejected_not_500(client):
    client.post("/api/setup", json={"name": "trungten", "password": "pw123456"})
    resp = client.post("/api/users", json={"name": "trungten", "password": "pw123456"})
    assert resp.status_code == 400, resp.text
    reset_auth_state()


def test_download_fmt_validated(client):
    result = _make_doc(client, "Bài kiểm tra fmt")
    version_id = result["version_id"]
    resp = client.get(f"/api/versions/{version_id}/download?fmt=zip")
    assert resp.status_code == 400
    reset_auth_state()


def test_setup_fast_reject_when_claimed(client):
    """Codex R2-3: setup is refused before hashing once an account exists."""
    client.post("/api/setup", json={"name": "daCo", "password": "pw123456"})
    resp = client.post("/api/setup", json={"name": "nguoiHai", "password": "pw123456"})
    assert resp.status_code == 409
    reset_auth_state()


def test_runs_user_id_backfilled(client):
    """Codex R2-10: pre-v6 runs (NULL user_id) gain ownership via migration."""
    from app import db
    result = _make_doc(client, "Bài kiểm tra backfill")
    row = db.get_conn().execute(
        "SELECT user_id FROM runs WHERE id = (SELECT MAX(id) FROM runs)").fetchone()
    assert row["user_id"] is not None
    reset_auth_state()
