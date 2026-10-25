"""Retrieval over the ingested dataset chunks.

Plan §2: filter by grade and subject first, then semantic search. Similarity is
plain cosine over embeddings stored in SQLite (numpy) — the dataset is small and
this avoids native vector-extension dependencies on Windows.
"""
import numpy as np

from . import db
from .embeddings import cosine, embed_query


def search(grade: str, subject: str, query: str, k: int = 6) -> list[dict]:
    rows = db.get_conn().execute(
        "SELECT id, source_file, grade, subject, doc_type, lesson, chunk_index, text, embedding"
        " FROM chunks WHERE grade = ? AND subject = ?",
        (grade, subject),
    ).fetchall()
    if not rows:
        # Graceful widening: try the same subject at any grade, then any chunk.
        rows = db.get_conn().execute(
            "SELECT id, source_file, grade, subject, doc_type, lesson, chunk_index, text, embedding"
            " FROM chunks WHERE subject = ?",
            (subject,),
        ).fetchall()
    if not rows:
        rows = db.get_conn().execute(
            "SELECT id, source_file, grade, subject, doc_type, lesson, chunk_index, text, embedding"
            " FROM chunks"
        ).fetchall()
    if not rows:
        return []

    q = embed_query(query)
    scored = [
        (cosine(q, np.frombuffer(r["embedding"], dtype=np.float32)), r) for r in rows
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    results = []
    for score, r in scored[:k]:
        if score <= 0.01:
            break
        results.append(
            {
                "score": round(score, 3),
                "source_file": r["source_file"],
                "doc_type": r["doc_type"],
                "lesson": r["lesson"],
                "text": r["text"],
            }
        )
    return results


def count_chunks() -> int:
    row = db.get_conn().execute("SELECT COUNT(*) AS n FROM chunks").fetchone()
    return int(row["n"])
