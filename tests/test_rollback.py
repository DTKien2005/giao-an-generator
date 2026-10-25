"""Version restore (non-destructive rollback) + conversation soft delete (v4)."""
import json
import time

from app import db
from app.diffing import diff_documents


def _wait_done(client, run_id):
    events = []
    deadline = time.time() + 30
    with client.stream("GET", f"/api/runs/{run_id}/events") as stream:
        for line in stream.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
                if events[-1]["type"] in ("done", "error"):
                    break
            if time.time() > deadline:
                break
    return events[-1]


def _make_document(client, lesson):
    resp = client.post("/api/generate", data={
        "grade": "grade_1", "subject": "toan", "lesson": lesson,
        "doc_type": "lesson_plan"})
    final = _wait_done(client, resp.json()["run_id"])
    assert final["type"] == "done", final
    return final["result"]


def test_restore_creates_identical_new_version(client):
    result = _make_document(client, "Bài thử phục hồi")
    doc_id = result["document_id"]
    v1_id = result["version_id"]

    # v2 via a small edit
    edit = _wait_done(client, client.post(
        f"/api/documents/{doc_id}/edit",
        data={"instruction": "sửa phần đánh giá chi tiết hơn"}).json()["run_id"])
    assert edit["type"] == "done"

    detail = client.get(f"/api/documents/{doc_id}").json()
    assert [v["version"] for v in detail["versions"]] == [2, 1]  # newest first

    # restore v1 -> becomes v3
    restore = _wait_done(client, client.post(
        f"/api/versions/{v1_id}/restore").json()["run_id"])
    assert restore["type"] == "done", restore
    assert restore["result"]["kind"] == "restore"

    detail = client.get(f"/api/documents/{doc_id}").json()
    assert [v["version"] for v in detail["versions"]] == [3, 2, 1]
    v3 = next(v for v in detail["versions"] if v["version"] == 3)
    v1 = next(v for v in detail["versions"] if v["version"] == 1)
    assert "Phục hồi từ v1" in v3["note"]
    assert v3["file_docx"] and v3["file_pdf"], "phiên bản phục hồi phải có tệp kết xuất"

    # restored content identical to the source version: empty diff
    old = client.get(f"/api/versions/{v1_id}/preview").json()
    new = client.get(f"/api/versions/{v3['id']}/preview").json()
    assert diff_documents(old, new) == []

    # conversation records the restore
    messages = detail["messages"]
    assert any("phục hồi" in m["content"].lower() for m in messages)


def test_restore_rejects_other_users_versions(client):
    # cross-user: make a second user and try restoring the first user's version
    from fastapi.testclient import TestClient
    from conftest import reset_auth_state
    from app.main import app

    if not db.get_conn().execute(
            "SELECT 1 FROM users WHERE password_hash != ''").fetchone():
        client.post("/api/setup", json={"name": "chuNha", "password": "pw123456"})
    client.post("/api/users", json={"name": "nguoiKhac", "password": "pw123456"})
    other = TestClient(app)
    other.post("/api/login", json={"name": "nguoiKhac", "password": "pw123456"})

    result = _make_document(client, "Bài không cho người khác phục hồi")
    resp = other.post(f"/api/versions/{result['version_id']}/restore")
    assert resp.status_code == 404
    reset_auth_state()  # back to open mode for the rest of the suite


def test_conversation_soft_delete(client):
    result = _make_document(client, "Bài xoá hội thoại")
    conv_id = result["conversation_id"]

    before = client.get("/api/conversations").json()
    assert any(c["id"] == conv_id for c in before)
    assert client.delete(f"/api/conversations/{conv_id}").status_code == 200

    after = client.get("/api/conversations").json()
    assert all(c["id"] != conv_id for c in after), "đã xoá phải ẩn khỏi danh sách"

    row = db.get_conn().execute(
        "SELECT deleted_at FROM conversations WHERE id = ?", (conv_id,)).fetchone()
    assert row["deleted_at"], "xoá mềm: dữ liệu vẫn còn trong DB"
    # document itself still directly reachable (not destroyed)
    assert client.get(f"/api/documents/{result['document_id']}").status_code == 200
