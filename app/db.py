"""SQLite access layer. Single-connection-per-thread, WAL mode, schema per plan §5/§8."""
import sqlite3
import threading
from contextlib import contextmanager

from . import config

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL DEFAULT 'Cuộc trò chuyện mới',
    summary TEXT NOT NULL DEFAULT '',      -- running LLM summary, not full history
    deleted_at TEXT,                       -- soft delete (v4): NULL = alive
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    title TEXT NOT NULL,
    doc_type TEXT NOT NULL,                -- lesson_plan | worksheet
    grade TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    format_spec TEXT NOT NULL DEFAULT '',  -- JSON: user's extracted layout (plan §3)
    latest_version_id INTEGER,             -- FK set after versions exist
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS document_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id),
    version INTEGER NOT NULL,
    content TEXT NOT NULL,                 -- full structured JSON of the document
    file_docx TEXT,
    file_pdf TEXT,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (document_id, version)
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER REFERENCES conversations(id),  -- nullable while queued
    document_id INTEGER REFERENCES documents(id),
    user_id INTEGER,                       -- owner (v6: run/SSE authorization)
    kind TEXT NOT NULL DEFAULT 'full',     -- full | small_edit
    status TEXT NOT NULL DEFAULT 'queued', -- queued | running | done | error
    progress TEXT NOT NULL DEFAULT '',     -- last SSE status line
    error TEXT,
    result_version_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS run_rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    round INTEGER NOT NULL,
    role TEXT NOT NULL,                    -- writer | reviewer | reviser
    payload TEXT NOT NULL,                 -- JSON: draft or review result
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chunks (        -- vector store for the dataset (plan §2)
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT NOT NULL,
    grade TEXT NOT NULL,
    subject TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    lesson TEXT NOT NULL DEFAULT '',
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    embedding BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_filter ON chunks (grade, subject);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL                    -- encrypted API keys stored here
);
"""


def get_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        config.ensure_dirs()
        conn = sqlite3.connect(config.DB_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


def init_db() -> None:
    conn = get_conn()
    conn.executescript(SCHEMA)
    _migrate(conn)
    # Sentinel row for open mode (no password): keeps FKs valid and holds all
    # pre-auth data; POST /api/setup later claims/renames this row.
    if not conn.execute("SELECT 1 FROM users WHERE id = 1").fetchone():
        conn.execute("INSERT INTO users (id, name, password_hash) VALUES (1, 'shared', '')")
    conn.commit()


def _migrate(conn: sqlite3.Connection) -> None:
    """Lightweight migrations for databases created before a feature existed."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
    if "password_hash" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT NOT NULL DEFAULT ''")
    conv_columns = {row[1] for row in conn.execute("PRAGMA table_info(conversations)")}
    if "deleted_at" not in conv_columns:
        conn.execute("ALTER TABLE conversations ADD COLUMN deleted_at TEXT")
    runs_columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}
    if "user_id" not in runs_columns:
        conn.execute("ALTER TABLE runs ADD COLUMN user_id INTEGER")
        # backfill ownership so pre-v6 runs stay accessible to their owners
        conn.execute(
            "UPDATE runs SET user_id = ("
            "  SELECT c.user_id FROM conversations c WHERE c.id = runs.conversation_id)"
            " WHERE user_id IS NULL AND conversation_id IS NOT NULL")
        conn.execute(
            "UPDATE runs SET user_id = ("
            "  SELECT c.user_id FROM documents d JOIN conversations c ON c.id = d.conversation_id"
            "  WHERE d.id = runs.document_id)"
            " WHERE user_id IS NULL AND document_id IS NOT NULL")


@contextmanager
def db():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
