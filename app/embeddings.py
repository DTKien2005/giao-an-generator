"""Text embeddings.

Primary: Gemini embeddings (`text-embedding-004`) when an API key is configured.
Fallback: deterministic hashed bag-of-words (unigrams + bigrams), L2-normalised.
The fallback keeps ingestion/retrieval/pipeline fully working offline (dev, tests,
no-key laptops) and is swapped out automatically once a key is present.
"""
import hashlib
import math
import re

import numpy as np

from . import config

_WORD = re.compile(r"\w+", re.UNICODE)


def _hash_embed(text: str) -> np.ndarray:
    vec = np.zeros(config.EMBEDDING_DIM, dtype=np.float32)
    words = _WORD.findall(text.lower())
    tokens = words + [f"{a}_{b}" for a, b in zip(words, words[1:])]
    for tok in tokens:
        h = int.from_bytes(hashlib.md5(tok.encode("utf-8")).digest()[:4], "little")
        vec[h % config.EMBEDDING_DIM] += 1.0
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec /= norm
    return vec


def _gemini_embed(texts: list[str]) -> list[np.ndarray]:
    import httpx

    url = f"{config.GEMINI_BASE_URL}/models/text-embedding-004:batchEmbedContents"
    body = {
        "requests": [
            {
                "model": "models/text-embedding-004",
                "content": {"parts": [{"text": t[:8000]}]},
            }
            for t in texts
        ]
    }
    resp = httpx.post(
        url, params={"key": _resolve_key()}, json=body, timeout=60
    )
    resp.raise_for_status()
    vectors = [np.array(e["values"], dtype=np.float32) for e in resp.json()["embeddings"]]
    return [_normalize(v) for v in vectors]


def _normalize(vec: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    return vec / norm if norm > 0 else vec


def _resolve_key() -> str:
    if config.GEMINI_API_KEY:
        return config.GEMINI_API_KEY
    try:
        from . import keys

        return keys.get_api_key("gemini")
    except Exception:
        return ""


def embed_texts(texts: list[str]) -> list[np.ndarray]:
    if not texts:
        return []
    if _resolve_key():
        try:
            return _gemini_embed(texts)
        except Exception:
            pass  # fall back below so ingestion never hard-fails offline
    return [_hash_embed(t) for t in texts]


def embed_query(text: str) -> np.ndarray:
    return embed_texts([text])[0]


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))
