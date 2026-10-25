"""Follow-up edit endpoint + version diffing (plan §5)."""
import json
import time

from app.diffing import diff_documents, flatten


def test_flatten_orders_sections():
    doc = {"sections": {
        "assessment": "Nhận xét.",
        "objectives": ["Đọc được.", "Viết được."],
        "activities": [{"name": "Khởi động", "minutes": 5,
                        "teacher": "Tổ chức trò chơi.", "students": "Tham gia."}],
    }}
    flat = flatten(doc)
    assert list(flat.keys()) == ["objectives", "activities", "assessment"]
    assert flat["objectives"] == ["Đọc được.", "Viết được."]
    assert "GV: Tổ chức trò chơi." in flat["activities"][0] or \
        flat["activities"][0].startswith("Khởi động")


def test_diff_documents_detects_added_and_removed():
    old = {"sections": {"objectives": ["Đọc được.", "Viết được."],
                        "assessment": "Nhận xét chung."}}
    new = {"sections": {"objectives": ["Đọc được.", "So sánh được."],
                        "assessment": "Nhận xét chung."}}
    sections = diff_documents(old, new)
    by_key = {s["section"]: s for s in sections}
    assert "objectives" in by_key
    ops = [(l["op"], l["text"]) for l in by_key["objectives"]["lines"]]
    assert ("removed", "Viết được.") in ops
    assert ("added", "So sánh được.") in ops
    assert "assessment" not in by_key  # unchanged sections are omitted


def _wait_run(client, run_id):
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
    return events


def test_edit_endpoint_creates_version_and_diff(client):
    # 1. create a document
    resp = client.post("/api/generate", data={
        "text": "Giáo án toán lớp 1", "doc_type": "lesson_plan",
        "grade": "grade_1", "subject": "toan", "lesson": "Bài teste chỉnh sửa",
    })
    run_id = resp.json()["run_id"]
    result = _wait_run(client, run_id)[-1]
    assert result["type"] == "done", result
    doc_id = result["result"]["document_id"]

    # 2. request a small edit through the chat endpoint
    resp = client.post(f"/api/documents/{doc_id}/edit",
                       data={"instruction": "sửa phần đánh giá cho chi tiết hơn"})
    assert resp.status_code == 200
    edit_events = _wait_run(client, resp.json()["run_id"])
    assert edit_events[-1]["type"] == "done"
    edit_result = edit_events[-1]["result"]
    assert edit_result["kind"] == "small"

    # 3. two versions now exist; diff endpoint shows the change
    detail = client.get(f"/api/documents/{doc_id}").json()
    assert len(detail["versions"]) == 2
    v1, v2 = sorted(detail["versions"], key=lambda v: v["version"])
    diff = client.get(f"/api/documents/{doc_id}/diff?from_version=1&to_version=2")
    assert diff.status_code == 200
    sections = diff.json()
    assert any(s["section"] for s in sections)

    # 4. conversation history shows both turns
    roles = [m["role"] for m in detail["messages"]]
    assert roles.count("user") >= 2 and roles.count("assistant") >= 2


def test_edit_endpoint_validates(client):
    resp = client.post("/api/documents/999999/edit", data={"instruction": "sửa gì đó"})
    assert resp.status_code == 404
