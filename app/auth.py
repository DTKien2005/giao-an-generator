"""Progressive authentication (PLANS.md §9 Phase 6).

No users → the app runs exactly as before (open mode). Once the first user is
created via POST /api/setup, every /api route except setup/login/me requires a
session cookie. Passwords: PBKDF2-HMAC-SHA256, 240k iterations, per-user salt.
"""
import hashlib
import hmac
import secrets

from . import db

_ITERATIONS = 240_000
_SESSION_DAYS = 7


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"pbkdf2${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, AttributeError):
        return False


def user_count() -> int:
    row = db.get_conn().execute(
        "SELECT COUNT(*) AS n FROM users WHERE password_hash != ''").fetchone()
    return int(row["n"])


def auth_enabled() -> bool:
    return user_count() > 0


def setup_first_user(name: str, password: str) -> int:
    """Claim the shared sentinel row as the first real account — all data
    created in open mode stays owned by this user."""
    if auth_enabled():
        raise PermissionError("Đã có người dùng — dùng /api/login")
    name = name.strip()
    if not name or not password:
        raise ValueError("Cần tên đăng nhập và mật khẩu")
    conn = db.get_conn()
    conn.execute(
        "UPDATE users SET name = ?, password_hash = ? WHERE id = 1",
        (name, hash_password(password)),
    )
    conn.execute("DELETE FROM sessions")
    conn.commit()
    return 1


def create_user(name: str, password: str) -> int:
    """Create a user; the *endpoints* decide who is allowed to call this
    (setup: only while no user exists; /api/users: any logged-in user)."""
    name = name.strip()
    if not name or not password:
        raise ValueError("Cần tên đăng nhập và mật khẩu")
    conn = db.get_conn()
    cur = conn.execute(
        "INSERT INTO users (name, password_hash) VALUES (?, ?)",
        (name, hash_password(password)),
    )
    conn.commit()
    return cur.lastrowid


def login(name: str, password: str) -> str | None:
    row = db.get_conn().execute(
        "SELECT id, password_hash FROM users WHERE name = ?", (name.strip(),)).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        return None
    token = secrets.token_urlsafe(32)
    conn = db.get_conn()
    conn.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?,"
        " datetime('now', ? || ' days'))",
        (token, row["id"], _SESSION_DAYS),
    )
    conn.commit()
    return token


def logout(token: str) -> None:
    conn = db.get_conn()
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()


def session_user(token: str | None):
    if not token:
        return None
    row = db.get_conn().execute(
        "SELECT u.id, u.name FROM sessions s JOIN users u ON u.id = s.user_id"
        " WHERE s.token = ? AND s.expires_at > datetime('now')",
        (token,),
    ).fetchone()
    return row
