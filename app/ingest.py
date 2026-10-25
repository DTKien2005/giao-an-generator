"""Dataset ingestion (plan §2): files + meta.json → chunks → embeddings → SQLite.

Usage: python -m app.ingest [--dataset DIR]

Handles .txt/.md (raw), .docx (python-docx) and .pdf (PyMuPDF text; scanned PDFs
are left to the operator — Gemini vision OCR is only worth wiring once real
scanned textbooks exist in the dataset).
"""
import argparse
import json
import re
from pathlib import Path

from . import config, db
from .embeddings import embed_texts

# Vietnamese section headings commonly used in textbooks and lesson plans.
_HEADING = re.compile(
    r"^(?:\s*)(?:[IVX]+\.|[A-ZĐÀÁẢÃẠÂẦẤẨẪẬÈÉẶẸỂẾỀỄỆÌÍĨỊĨÒÓÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚŨỤƯỪỨỬỮỰỲÝỶỸỴ]\.|"
    r"Bài\s+\d+|Hoạt\s+động\s+\d+|CHƯƠNG\s+\d+|Chương\s+\d+)",
    re.UNICODE,
)
MAX_CHUNK_CHARS = 1600


def file_to_text(path: Path) -> str:
    """Text content of a file; scanned-PDF pages are OCR'd when possible."""
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".docx":
        import docx

        parts = [p.text for p in docx.Document(str(path)).paragraphs]
        for table in docx.Document(str(path)).tables:
            for row in table.rows:
                parts.append("\t".join(c.text for c in row.cells))
        return "\n".join(parts)
    if suffix == ".pdf":
        from .ocr import extract_pdf_text

        text, _warnings = extract_pdf_text(path)
        return text
    raise ValueError(f"Unsupported file type: {path.suffix}")


def chunk_text(text: str) -> list[str]:
    """Split on lesson/section headings; merge tiny pieces, split oversized ones."""
    lines = text.splitlines()
    sections: list[list[str]] = [[]]
    for line in lines:
        if _HEADING.match(line) and sections[-1]:
            sections.append([])
        sections[-1].append(line)
    chunks = ["\n".join(s).strip() for s in sections]
    chunks = [c for c in chunks if c]

    merged: list[str] = []
    for chunk in chunks:
        while len(chunk) > MAX_CHUNK_CHARS:
            cut = chunk.rfind("\n", 0, MAX_CHUNK_CHARS)
            cut = cut if cut > 200 else MAX_CHUNK_CHARS
            merged.append(chunk[:cut].strip())
            chunk = chunk[cut:].strip()
        if len(chunk) < 80 and merged:
            merged[-1] += "\n" + chunk
        elif chunk:
            merged.append(chunk)
    return merged


def ingest(dataset_dir: Path | None = None) -> dict:
    dataset_dir = dataset_dir or config.DATASET_DIR
    conn = db.get_conn()
    conn.execute("DELETE FROM chunks")
    stats = {"files": 0, "chunks": 0, "skipped": []}

    files = sorted(
        p
        for p in dataset_dir.rglob("*")
        if p.suffix.lower() in (".txt", ".md", ".docx", ".pdf") and p.is_file()
    )
    batch_texts: list[str] = []
    batch_meta: list[dict] = []

    def flush() -> None:
        nonlocal batch_texts, batch_meta
        if not batch_texts:
            return
        vectors = embed_texts(batch_texts)
        for text, meta, vec in zip(batch_texts, batch_meta, vectors):
            conn.execute(
                "INSERT INTO chunks (source_file, grade, subject, doc_type, lesson,"
                " chunk_index, text, embedding) VALUES (?,?,?,?,?,?,?,?)",
                (
                    meta["source_file"], meta["grade"], meta["subject"],
                    meta["doc_type"], meta["lesson"], meta["chunk_index"],
                    text, vec.tobytes(),
                ),
            )
            stats["chunks"] += 1
        batch_texts, batch_meta = [], []

    for path in files:
        meta_path = path.with_suffix(path.suffix + ".meta.json")
        meta = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                stats["skipped"].append(f"{path.name} (bad meta.json)")
                continue
        # Fallback derivation from the folder layout: dataset/grade_X/subject/type/file
        rel = path.relative_to(dataset_dir)
        parts = rel.parts
        grade = meta.get("grade") or (parts[0] if len(parts) >= 3 and parts[0].startswith("grade_") else "")
        subject = meta.get("subject") or (parts[1] if len(parts) >= 3 else "")
        doc_type = meta.get("doc_type") or (
            {"textbooks": "textbook", "lesson_plans": "lesson_plan",
             "worksheets": "worksheet"}.get(parts[2], parts[2]) if len(parts) >= 3 else ""
        )
        try:
            if path.suffix.lower() == ".pdf":
                from .ocr import extract_pdf_text

                text, warnings = extract_pdf_text(path)
                stats["skipped"].extend(warnings)  # scanned pages skipped, per page
            else:
                text = file_to_text(path)
        except Exception as exc:
            stats["skipped"].append(f"{path.name} ({exc})")
            continue
        if not text.strip():
            stats["skipped"].append(f"{path.name} (empty)")
            continue
        stats["files"] += 1
        for i, chunk in enumerate(chunk_text(text)):
            batch_texts.append(chunk)
            batch_meta.append({
                "source_file": str(rel), "grade": grade, "subject": subject,
                "doc_type": doc_type, "lesson": meta.get("lesson", ""),
                "chunk_index": i,
            })
        if len(batch_texts) >= 32:
            flush()
    flush()
    conn.commit()
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest the dataset into the vector store")
    parser.add_argument("--dataset", type=Path, default=None)
    args = parser.parse_args()
    db.init_db()
    print(json.dumps(ingest(args.dataset), ensure_ascii=False, indent=2))
