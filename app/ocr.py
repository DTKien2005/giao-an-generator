"""OCR for scanned PDFs via Gemini vision (PLANS.md §3.1).

Only used when a PDF page has no text layer. Without a Gemini key the page is
skipped with a warning — ingestion never fails because of a scan.
"""
import base64

OCR_MODEL = "gemini-2.5-flash"
OCR_PROMPT = (
    "Transcribe exactly all Vietnamese text in this document page image. "
    "Keep the original line structure and headings. Output only the transcribed text."
)


def page_has_text(page) -> bool:
    return len(page.get_text().strip()) >= 20


def render_page_png(page, dpi: int = 150) -> bytes:
    pix = page.get_pixmap(dpi=dpi)
    return pix.tobytes("png")


def _gemini_ocr_image(image_png: bytes) -> str:
    """One Gemini vision call. Raises if no key or on transport errors."""
    import httpx

    from . import config, keys

    key = keys.get_api_key("gemini")
    if not key:
        raise RuntimeError("Chưa cấu hình khoá Gemini cho OCR")
    body = {
        "contents": [{
            "role": "user",
            "parts": [
                {"inline_data": {"mime_type": "image/png",
                                 "data": base64.b64encode(image_png).decode("ascii")}},
                {"text": OCR_PROMPT},
            ],
        }],
        "generationConfig": {"maxOutputTokens": 4096, "temperature": 0.0},
    }
    resp = httpx.post(
        f"{config.GEMINI_BASE_URL}/models/{OCR_MODEL}:generateContent",
        params={"key": key}, json=body, timeout=120,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini OCR HTTP {resp.status_code}: {resp.text[:200]}")
    try:
        return "".join(p.get("text", "")
                       for p in resp.json()["candidates"][0]["content"]["parts"])
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Gemini OCR phản hồi lạ: {resp.text[:200]}") from exc


def extract_pdf_text(path, ocr_fn=_gemini_ocr_image) -> tuple[str, list[str]]:
    """Per-page text; scanned pages go through `ocr_fn` when possible.

    Returns (text, warnings). Never raises for unOCR-able pages — those pages
    are skipped and reported in warnings.
    """
    import pymupdf

    warnings: list[str] = []
    parts: list[str] = []
    with pymupdf.open(str(path)) as pdf:
        for i, page in enumerate(pdf, start=1):
            if page_has_text(page):
                parts.append(page.get_text())
                continue
            try:
                parts.append(ocr_fn(render_page_png(page)))
            except RuntimeError as exc:
                warnings.append(f"{path.name} trang {i}: bỏ qua ({exc})")
    return "\n".join(parts), warnings
