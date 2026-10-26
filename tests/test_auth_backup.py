"""Auth (progressive) and backups (v3).

IMPORTANT: tests that enable auth MUST clean up (delete users/sessions) — the
suite shares one database, and leftover accounts would 401 every other test.
"""
import zipfile

from fastapi.testclient import TestClient

from conftest import reset_auth_state
from app import auth, backup, db
from app.main import app

_reset_auth_state = reset_auth_state


def test_open_mode_without_users():
    """No account → everything works exactly as before (open mode)."""
    _reset_auth_state()
    with TestClient(app) as client:
        assert client.get("/api/conversations").status_code == 200
        me = client.get("/api/me").json()
        assert me["name"] is None and me["auth_enabled"] is False
        assert me["setup_token_required"] is False


def test_setup_login_logout_and_protection():
    _reset_auth_state()
    with TestClient(app) as client:
        # 1. setup claims the shared account
        resp = client.post("/api/setup", json={"name": "coCham", "password": "matkhau123"})
        assert resp.status_code == 200, resp.text
        assert client.get("/api/me").json()["name"] == "coCham"

        # 2. second setup refused
        assert client.post("/api/setup", json={"name": "x", "password": "y2345678"}).status_code == 409

        # 3. anonymous client is locked out, /api/me stays public
        anon = TestClient(app)
        assert anon.get("/api/conversations").status_code == 401
        assert anon.get("/api/me").json()["auth_enabled"] is True
        assert anon.get("/api/me").json()["setup_token_required"] is False

        # 4. wrong password refused
        bad = TestClient(app)
        assert bad.post("/api/login", json={"name": "coCham", "password": "sai"}).status_code == 401

        # 5. isolation: another user cannot see coCham's data
        client.post("/api/users", json={"name": "hocSinh", "password": "pass1234"})
        other = TestClient(app)
        other.post("/api/login", json={"name": "hocSinh", "password": "pass1234"})
        resp = client.post("/api/generate", data={
            "grade": "grade_1", "subject": "toan", "lesson": "Bài riêng của coCham",
            "doc_type": "lesson_plan"})
        assert resp.status_code == 200
        import json as _json
        import time
        run_id = resp.json()["run_id"]
        events = []
        deadline = time.time() + 30
        with client.stream("GET", f"/api/runs/{run_id}/events") as stream:
            for line in stream.iter_lines():
                if line.startswith("data: "):
                    events.append(_json.loads(line[6:]))
                    if events[-1]["type"] in ("done", "error"):
                        break
                if time.time() > deadline:
                    break
        doc_id = events[-1]["result"]["document_id"]

        my_convs = client.get("/api/conversations").json()
        their_convs = other.get("/api/conversations").json()
        my_ids = {c["id"] for c in my_convs}
        assert any(c["documents"] >= 1 for c in my_convs), "tài liệu mới phải hiện với chủ sở hữu"
        assert all(c["id"] not in my_ids for c in their_convs)
        assert other.get(f"/api/documents/{doc_id}").status_code == 404
        assert client.get(f"/api/documents/{doc_id}").status_code == 200

        # 6. logout invalidates the session
        client.post("/api/logout")
        assert client.get("/api/conversations").status_code == 401

    _reset_auth_state()


def test_password_hashing_properties():
    h1 = auth.hash_password("abc")
    h2 = auth.hash_password("abc")
    assert h1 != h2  # unique salt per hash
    assert auth.verify_password("abc", h1)
    assert not auth.verify_password("abd", h1)
    assert not auth.verify_password("abc", "rác")


def test_backup_creates_zip_with_database_and_rotation():
    config_keep = backup.KEEP
    backup.KEEP = 3
    try:
        paths = [backup.create_backup()[0] for _ in range(5)]
        with zipfile.ZipFile(paths[-1]) as zf:
            names = zf.namelist()
        assert "app.db" in names
        remaining = sorted((paths[-1].parent).glob("backup_*.zip"))
        assert len(remaining) == 3, "phải giữ đúng 3 bản gần nhất"
    finally:
        backup.KEEP = config_keep
        for stale in paths[0].parent.glob("backup_*.zip"):
            stale.unlink(missing_ok=True)
