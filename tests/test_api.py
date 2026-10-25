"""API surface via TestClient: generate → SSE → documents → download."""
import json
import time

# `client` fixture comes from conftest.py (session-scoped).


def _generate_and_wait(client, payload=None, files=None):
    data = payload or {
        "text": "Giáo án toán lớp 1 bài các số có hai chữ số",
        "doc_type": "lesson_plan", "grade": "grade_1", "subject": "toan",
        "lesson": "Các số có hai chữ số api test",
    }
    resp = client.post("/api/generate", data=data, files=files)
    assert resp.status_code == 200, resp.text
    run_id = resp.json()["run_id"]

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
    return run_id, events


def test_index_served(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Soạn" in resp.text


def test_generate_requires_some_input(client):
    resp = client.post("/api/generate", data={"text": "", "lesson": ""})
    assert resp.status_code == 400


def test_generate_streams_progress_and_finishes(client):
    run_id, events = _generate_and_wait(client)
    types = [e["type"] for e in events]
    assert "progress" in types
    assert types[-1] == "done"
    result = events[-1]["result"]
    assert result["document"]["sections"].get("appendix")

    status = client.get(f"/api/runs/{run_id}").json()
    assert status["status"] == "done"
    assert status["result_version_id"] == result["version_id"]


def test_document_versions_and_downloads(client):
    _, events = _generate_and_wait(client)
    result = events[-1]["result"]
    doc_id = result["document_id"]

    detail = client.get(f"/api/documents/{doc_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["document"]["title"]
    assert len(body["versions"]) == 1
    version_id = body["versions"][0]["id"]

    preview = client.get(f"/api/versions/{version_id}/preview").json()
    assert preview["doc_type"] == "lesson_plan"

    for fmt in ("docx", "pdf"):
        dl = client.get(f"/api/versions/{version_id}/download?fmt={fmt}")
        assert dl.status_code == 200, fmt
        assert len(dl.content) > 1000


def test_conversations_listing(client):
    _generate_and_wait(client)
    resp = client.get("/api/conversations")
    assert resp.status_code == 200
    rows = resp.json()
    assert rows, "phải có ít nhất một cuộc trò chuyện"
    conv_id = rows[0]["id"]
    docs = client.get(f"/api/conversations/{conv_id}/documents").json()
    assert docs


def test_upload_docx_used_as_source(client, tmp_path):
    # build a small .docx upload on the fly
    import docx as docx_lib
    path = tmp_path / "de_bai.docx"
    d = docx_lib.Document()
    d.add_paragraph("Giáo án toán lớp 1 bài các số có hai chữ số (từ tệp tải lên)")
    d.save(str(path))
    with open(path, "rb") as f:
        _, events = _generate_and_wait(
            client,
            payload={"doc_type": "lesson_plan", "lesson": "Các số có hai chữ số upload test"},
            files={"file": ("de_bai.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
    assert events[-1]["type"] == "done"
