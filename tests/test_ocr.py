"""OCR routing tests (v2): text-layer PDFs go direct; scanned pages OCR when a
key/mock is available, skip safely otherwise. No network calls in tests."""
import base64

import pymupdf

from app import ocr
from app.ocr import extract_pdf_text, render_page_png


def _pdf_with_text_layer(path):
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        # insert_htmlbox embeds real Unicode text (default base-14 fonts lack
        # Vietnamese glyphs and would extract as '?')
        page.insert_htmlbox(pymupdf.Rect(50, 50, 500, 200),
                            "GIÁO ÁN TOÁN LỚP 1<br/>Bài dạy: Các số có hai chữ số")
        pdf.save(str(path))


def _scanned_pdf(path):
    """A page whose only content is a PNG image of text — no text layer."""
    with pymupdf.open() as src:
        page = src.new_page()
        page.insert_htmlbox(pymupdf.Rect(50, 50, 500, 200),
                            "GIÁO ÁN TOÁN LỚP 2<br/>Bài dạy: Phép cộng không nhớ")
        png = page.get_pixmap(dpi=150).tobytes("png")
    with pymupdf.open() as pdf:
        out_page = pdf.new_page()
        out_page.insert_image(out_page.rect, stream=png)
        pdf.save(str(path))


def test_text_layer_pdf_never_calls_ocr(tmp_path, monkeypatch):
    pdf_path = tmp_path / "co_lop_chu.pdf"
    _pdf_with_text_layer(pdf_path)

    def boom(_img):
        raise AssertionError("không được gọi OCR cho PDF có lớp chữ")

    text, warnings = extract_pdf_text(pdf_path, ocr_fn=boom)
    assert "hai chữ số" in text
    assert warnings == []


def test_scanned_pdf_skipped_safely_without_key(tmp_path):
    pdf_path = tmp_path / "quet.pdf"
    _scanned_pdf(pdf_path)
    text, warnings = extract_pdf_text(pdf_path)  # no key in test env → real ocr_fn
    assert text.strip() == ""          # nothing recoverable offline
    assert len(warnings) == 1 and "trang 1" in warnings[0]


def test_scanned_pdf_ocr_via_injected_fn(tmp_path):
    pdf_path = tmp_path / "quet2.pdf"
    _scanned_pdf(pdf_path)

    def fake_ocr(png_bytes: bytes) -> str:
        assert png_bytes[:4] == b"\x89PNG"  # rendered image, not the page text
        return "GIÁO ÁN TOÁN LỚP 2\nBài dạy: Phép cộng không nhớ (đã OCR)"

    text, warnings = extract_pdf_text(pdf_path, ocr_fn=fake_ocr)
    assert "đã OCR" in text
    assert warnings == []


def test_gemini_ocr_request_shape(monkeypatch):
    """The live path builds a proper inline_data vision request."""
    captured = {}

    class FakeResp:
        status_code = 200

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "văn bản"}]}}]}

    def fake_post(url, params=None, json=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["body"] = json
        return FakeResp()

    import httpx

    import app.ocr as ocr_mod
    import app.keys as keys_mod
    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(keys_mod, "get_api_key", lambda p: "fake-key")

    png = _blank_png()
    result = ocr_mod._gemini_ocr_image(png)

    assert result == "văn bản"
    assert "generateContent" in captured["url"]
    part = captured["body"]["contents"][0]["parts"][0]
    assert part["inline_data"]["mime_type"] == "image/png"
    assert base64.b64decode(part["inline_data"]["data"])[:4] == b"\x89PNG"


def _blank_png() -> bytes:
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        return render_page_png(page)


def test_ingest_reports_skipped_scanned_pages(tmp_path, monkeypatch):
    scanned = tmp_path / "sgk_quet.pdf"
    _scanned_pdf(scanned)
    from app import ingest

    try:
        stats = ingest.ingest(tmp_path)  # rebuilds the whole chunk index…
        assert stats["files"] == 0
        assert any("trang 1" in s for s in stats["skipped"])
    finally:
        ingest.ingest()  # …so restore the real dataset for the other tests
