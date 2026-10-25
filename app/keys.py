"""API key storage and model settings (plan §6 / Phase 5).

Keys are encrypted at rest with Fernet; the key file lives in the data dir and
is generated on first use. Per-role models and the default provider live in the
same `settings` table as plain JSON values.
"""
import json

from . import config, db

_PROVIDERS = ("gemini", "openai", "anthropic", "local", "mock")
_ROLES = ("writer", "reviewer", "reviser", "intake")

_fernet = None


def _fernet_instance():
    global _fernet
    if _fernet is not None:
        return _fernet
    from cryptography.fernet import Fernet, InvalidToken

    config.ensure_dirs()
    key_path = config.DATA_DIR / "secret.key"
    if key_path.exists():
        key = key_path.read_bytes()
    else:
        key = Fernet.generate_key()
        key_path.write_bytes(key)
    _fernet = Fernet(key)
    return _fernet


def encrypt(text: str) -> str:
    return _fernet_instance().encrypt(text.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    from cryptography.fernet import InvalidToken

    try:
        return _fernet_instance().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        return ""


# ---------------------------------------------------------------------------
# Settings access (settings table)
# ---------------------------------------------------------------------------

def _get(key: str) -> str | None:
    row = db.get_conn().execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def _set(key: str, value: str) -> None:
    db.get_conn().execute(
        "INSERT INTO settings (key, value) VALUES (?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    db.get_conn().commit()


def get_api_key(provider: str) -> str:
    """Stored key (decrypted) first; environment variable as fallback."""
    token = _get(f"provider:{provider}:key")
    if token:
        key = decrypt(token)
        if key:
            return key
    env_names = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY",
                 "anthropic": "ANTHROPIC_API_KEY"}
    import os

    return os.environ.get(env_names.get(provider, ""), "")


def set_api_key(provider: str, key: str) -> None:
    _set(f"provider:{provider}:key", encrypt(key) if key else "")


def get_default_provider() -> str:
    provider = _get("provider:default")
    if provider in _PROVIDERS:
        return provider
    return config.DEFAULT_PROVIDER


def set_default_provider(provider: str) -> None:
    if provider not in _PROVIDERS:
        raise ValueError(f"Provider không hỗ trợ: {provider}")
    _set("provider:default", provider)


def get_base_url(provider: str) -> str:
    """Custom base URL (Ollama / LM Studio / vLLM — any OpenAI-compatible server)."""
    if provider == "openai":
        return _get("provider:openai:base_url") or "https://api.openai.com/v1"
    if provider == "anthropic":
        return _get("provider:anthropic:base_url") or "https://api.anthropic.com"
    if provider == "local":
        return _get("provider:local:base_url") or "http://localhost:11434/v1"
    return ""


def set_base_url(provider: str, url: str) -> None:
    _set(f"provider:{provider}:base_url", url)


def get_model(role: str) -> str:
    """Per-role model (plan §6: Writer / Reviewer / Reviser chosen separately)."""
    model = _get(f"model:{role}")
    return model or config.DEFAULT_MODELS.get(role, "gemini-2.5-flash")


def set_model(role: str, model: str) -> None:
    if role not in _ROLES:
        raise ValueError(f"Role không hợp lệ: {role}")
    _set(f"model:{role}", model)


def settings_summary() -> dict:
    """Everything the settings UI shows — keys only as booleans, never plaintext."""
    return {
        "default_provider": get_default_provider(),
        "providers": list(_PROVIDERS),
        "roles": list(_ROLES),
        "models": {role: get_model(role) for role in _ROLES},
        "keys_set": {p: bool(get_api_key(p)) for p in ("gemini", "openai", "anthropic")},
        "base_urls": {p: get_base_url(p) for p in ("openai", "anthropic", "local")},
    }
