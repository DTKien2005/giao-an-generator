"""Test setup: isolate data dir, force the mock provider, ingest the dataset once."""
import os
import sys
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="ga_test_")
os.environ["APP_DATA_DIR"] = _TMP
os.environ["DEFAULT_PROVIDER"] = "mock"
os.environ["APP_RATE_LIMIT"] = "500"  # tests fire many runs; the limit itself is tested separately
os.environ.pop("GEMINI_API_KEY", None)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db, ingest  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _init_database():
    db.init_db()
    ingest.ingest()
    yield


def reset_auth_state():
    """Return the suite to open mode after a test enabled auth. Deletes
    dependent rows in FK order and never leaves an open transaction behind
    (a failed cleanup once held a write lock and broke every later test)."""
    conn = db.get_conn()
    try:
        for table in ("run_rounds", "jobs", "runs", "messages", "document_versions",
                      "documents", "conversations", "sessions", "users"):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("INSERT INTO users (id, name, password_hash) VALUES (1, 'shared', '')")
        conn.commit()
    except Exception:
        conn.rollback()
        raise


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:  # context manager → lifespan → db.init_db()
        yield c
