"""Retrieval over the ingested dataset."""
import numpy as np

from app import db
from app.embeddings import embed_texts, embed_query, cosine
from app.retrieve import count_chunks, search


def test_dataset_ingested():
    assert count_chunks() >= 20  # 6 seed files → ≥30 chunks


def test_hash_embedding_deterministic_and_normalized():
    a1 = embed_query("giáo án toán lớp 1")
    a2 = embed_query("giáo án toán lớp 1")
    assert np.allclose(a1, a2)
    assert abs(np.linalg.norm(a1) - 1.0) < 1e-5


def test_similar_texts_closer_than_unrelated():
    texts = embed_texts(["phép cộng hai số có hai chữ số", "cộng các số tròn chục",
                         "tập đọc tiếng việt bài mái trường"])
    assert cosine(texts[0], texts[1]) > cosine(texts[0], texts[2])


def test_search_filters_by_grade_and_subject():
    hits = search("grade_1", "toan", "các số có hai chữ số", k=5)
    assert hits, "phải tìm thấy chunk cho grade_1/toan"
    top = hits[0]
    assert "hai chữ số" in top["text"].lower()
    assert top["source_file"].startswith("grade_1")


def test_search_widens_when_bucket_empty():
    # grade_9 has no chunks — must widen instead of returning nothing
    hits = search("grade_9", "toan", "các số có hai chữ số", k=3)
    assert hits
