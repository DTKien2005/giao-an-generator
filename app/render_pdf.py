"""Render a document (structured JSON) to PDF.

Preferred path per plan §7 is headless LibreOffice (so .docx and .pdf always
match); when LibreOffice is absent — as on this machine — fall back to
reportlab with a Vietnamese-capable TrueType font (Times New Roman).
"""
import shutil
import subprocess
from pathlib import Path

from . import config
from .formats import resolve_title

_font_registered = False


def _register_font():
    global _font_registered
    if _font_registered:
        return
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.pdfmetrics import registerFontFamily

    # The vendored font (full Vietnamese diacritics, OFL) ships with the repo,
    # so rendering is identical on Windows / Linux / Docker / CI. System fonts
    # are only a fallback if the asset ever goes missing.
    repo_font = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "IBMPlexSerif-Regular.ttf"
    repo_bold = repo_font.with_name("IBMPlexSerif-Bold.ttf")
    candidates = [repo_font] + [Path(p) for p in config.PDF_FONT_CANDIDATES]

    for candidate in candidates:
        if candidate.exists():
            pdfmetrics.registerFont(TTFont("VNFont", str(candidate)))
            if candidate == repo_font and repo_bold.exists():
                pdfmetrics.registerFont(TTFont("VNFont-Bold", str(repo_bold)))
                registerFontFamily("VNFont", normal="VNFont", bold="VNFont-Bold",
                                   italic="VNFont", boldItalic="VNFont-Bold")
            _font_registered = True
            return
    raise RuntimeError("Không tìm thấy font tiếng Việt cho PDF (assets/fonts hoặc Times New Roman)")


def _soffice_path() -> str | None:
    for candidate in config.SOFFICE_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return shutil.which("soffice")


def render_pdf(document: dict, format_spec: dict, docx_path: Path, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    soffice = _soffice_path()
    if soffice:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf",
             "--outdir", str(out_path.parent), str(docx_path)],
            check=True, capture_output=True, timeout=120,
        )
        converted = out_path.parent / (docx_path.stem + ".pdf")
        if converted.exists():
            if converted != out_path:
                shutil.move(str(converted), str(out_path))
            return out_path
    return _render_reportlab(document, format_spec, out_path)


def _render_reportlab(document: dict, format_spec: dict, out_path: Path) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    _register_font()
    styles = {
        "title": ParagraphStyle("title", fontName="VNFont", fontSize=14, alignment=1,
                                spaceAfter=6, leading=18),
        "sub": ParagraphStyle("sub", fontName="VNFont", fontSize=12, alignment=1,
                              spaceAfter=2, leading=16),
        "heading": ParagraphStyle("heading", fontName="VNFont", fontSize=12,
                                  spaceBefore=10, spaceAfter=4, leading=16),
        "body": ParagraphStyle("body", fontName="VNFont", fontSize=12, leading=16),
        "bullet": ParagraphStyle("bullet", fontName="VNFont", fontSize=12, leftIndent=16,
                                 bulletIndent=6, leading=16),
        "cell": ParagraphStyle("cell", fontName="VNFont", fontSize=11, leading=14),
    }

    story = [Paragraph(resolve_title(format_spec, document), styles["title"])]
    if document.get("lesson"):
        story.append(Paragraph(f"<b>Bài dạy: {document['lesson']}</b>", styles["sub"]))
    if document.get("week"):
        story.append(Paragraph(f"Tuần: {document['week']}", styles["sub"]))
    story.append(Spacer(1, 8))

    sections = document.get("sections", {})
    for spec_section in format_spec.get("sections", []):
        sid = spec_section["id"]
        content = sections.get(sid)
        if content in (None, "", [], {}):
            continue
        label = spec_section.get("label", "")
        if label:
            story.append(Paragraph(f"<b>{label}</b>", styles["heading"]))
        stype = spec_section.get("type", "text")
        if stype == "bullets":
            for item in content:
                story.append(Paragraph(str(item), styles["bullet"], bulletText="•"))
        elif stype == "activities":
            story.append(_activity_table(content))
            story.append(Spacer(1, 6))
        elif stype == "exercises":
            for ex in content:
                story.append(Paragraph(f"<b>{ex.get('title', '')}</b>", styles["body"]))
                story.append(Paragraph(ex.get("content", ""), styles["body"]))
        elif isinstance(content, list):
            for line in content:
                story.append(Paragraph(str(line), styles["body"]))
        else:
            story.append(Paragraph(str(content).replace("\n", "<br/>"), styles["body"]))

    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2.5 * cm, rightMargin=2.5 * cm,
        title=resolve_title(format_spec, document),
    )
    doc.build(story)
    return out_path


def _activity_table(activities: list[dict]):
    from reportlab.lib.units import cm
    from reportlab.platypus import Table, TableStyle

    data = [["Hoạt động", "Nội dung", "Thời lượng"]]
    for act in activities:
        data.append([
            act.get("name", ""),
            f"Giáo viên: {act.get('teacher', '')}<br/>Học sinh: {act.get('students', '')}",
            f"{act.get('minutes', '')} phút",
        ])
    table = Table(
        data, colWidths=[3.5 * cm, 10 * cm, 2.5 * cm],
        style=TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.6, (0.4, 0.4, 0.4)),
            ("BACKGROUND", (0, 0), (-1, 0), (0.9, 0.9, 0.95)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTNAME", (0, 0), (-1, -1), "VNFont"),
            ("FONTSIZE", (0, 0), (-1, -1), 11),
        ]),
    )
    return table
