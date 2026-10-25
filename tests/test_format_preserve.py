"""Plan §3.3/§3.4: user's own format takes priority; the extracted spec is cached."""
import json
import time

import docx as docx_lib

USER_LESSON_PLAN = """\
GIÁO ÁN RIÊNG CỦA TÔI
Bài dạy: phép cộng

I. MỤC TIÊU
- Biết làm phép cộng.

III. CÁC HOẠT ĐỘNG DẠY HỌC
Hoạt động 1. Khởi động

IV. ĐÁNH GIÁ
- Nhận xét.
"""


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


def _upload(tmp_path, content=USER_LESSON_PLAN):
    path = tmp_path / "mau_giao_an.docx"
    d = docx_lib.Document()
    for line in content.splitlines():
        d.add_paragraph(line)
    d.save(str(path))
    return path


def test_upload_sets_and_caches_user_format(client, tmp_path):
    path = _upload(tmp_path)
    with open(path, "rb") as f:
        resp = client.post("/api/generate", data={
            "doc_type": "", "grade": "grade_2", "subject": "toan",
            "lesson": "Phép cộng không nhớ",
        }, files={"file": ("mau_giao_an.docx", f,
                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert resp.status_code == 200
    final = _wait_done(client, resp.json()["run_id"])
    assert final["type"] == "done", final
    doc_id = final["result"]["document_id"]

    detail = client.get(f"/api/documents/{doc_id}").json()
    spec = json.loads(detail["document"]["format_spec"])
    assert spec.get("source") == "user_upload"
    ids = [s["id"] for s in spec["sections"]]
    assert ids == ["objectives", "activities", "assessment"]  # upload's own order
    # the rendered docx only contains the sections the user's format defines
    import pymupdf
    pdf_path = detail["versions"][0]["file_pdf"]
    with pymupdf.open(pdf_path) as pdf:
        text = pdf[0].get_text()
    assert "MỤC TIÊU" in text and "ĐÁNH GIÁ" in text
    assert "ĐỒ DÙNG DẠY HỌC" not in text  # not in the user's format

    # plan §3.4: cached — a later request without upload reuses it
    resp = client.post("/api/generate", data={
        "doc_type": "lesson_plan", "grade": "grade_2", "subject": "toan",
        "lesson": "Phép cộng có nhớ trong phạm vi 100",
    })
    final2 = _wait_done(client, resp.json()["run_id"])
    assert final2["type"] == "done"
    detail2 = client.get(f"/api/documents/{final2['result']['document_id']}").json()
    spec2 = json.loads(detail2["document"]["format_spec"])
    assert spec2.get("source") == "user_upload"


def test_cached_lesson_plan_spec_not_applied_to_worksheets(client, tmp_path):
    path = _upload(tmp_path)
    with open(path, "rb") as f:
        client.post("/api/generate", data={
            "grade": "grade_2", "subject": "toan", "lesson": "Đặt lại định dạng mẫu",
        }, files={"file": ("mau_giao_an.docx", f,
                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    resp = client.post("/api/generate", data={
        "doc_type": "worksheet", "grade": "grade_2", "subject": "toan",
        "lesson": "Phiếu tuần 9", "week": "9",
    })
    final = _wait_done(client, resp.json()["run_id"])
    assert final["type"] == "done"
    detail = client.get(f"/api/documents/{final['result']['document_id']}").json()
    spec = json.loads(detail["document"]["format_spec"])
    assert spec.get("doc_type") == "worksheet"  # default worksheet template, not the user's plan
