"""Application settings. Everything overridable via environment variables."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("APP_DATA_DIR", BASE_DIR / "data"))
DATASET_DIR = Path(os.environ.get("APP_DATASET_DIR", BASE_DIR / "dataset"))
DB_PATH = DATA_DIR / "app.db"
GENERATED_DIR = DATA_DIR / "generated"  # rendered .docx/.pdf per version
UPLOADS_DIR = DATA_DIR / "uploads"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
EMBEDDING_DIM = 256  # fallback hashed-embedding dimension (offline dev/tests)

# Per-role model defaults; user can override in Settings UI.
DEFAULT_MODELS = {
    "writer": os.environ.get("MODEL_WRITER", "gemini-2.5-flash"),
    "reviewer": os.environ.get("MODEL_REVIEWER", "gemini-2.5-flash"),
    "reviser": os.environ.get("MODEL_REVISER", "gemini-2.5-flash"),
    "intake": os.environ.get("MODEL_INTAKE", "gemini-2.5-flash"),
}
DEFAULT_PROVIDER = os.environ.get("DEFAULT_PROVIDER", "gemini" if GEMINI_API_KEY else "mock")

MAX_ROUNDS = 3          # hard cap on review rounds (plan §10)
PASS_SCORE = 8.0        # average score needed to stop early
MAX_TOKENS_PER_CALL = 8192
RATE_LIMIT_RUNS = int(os.environ.get("APP_RATE_LIMIT", "10"))   # cost cap (plan §10)
RATE_LIMIT_WINDOW = 600  # seconds

# v6 go-live (PLANS_V6.md): trust Cloudflare's CF-Connecting-IP from loopback,
# optional first-account setup token, Secure session cookie in production.
TRUST_PROXY = os.environ.get("APP_TRUST_PROXY", "") == "1"
SETUP_TOKEN = os.environ.get("APP_SETUP_TOKEN", "")
COOKIE_SECURE = os.environ.get("APP_COOKIE_SECURE", "") == "1"
BACKUP_COPY_DIR = os.environ.get("APP_BACKUP_COPY_DIR", "")

# Fallback system fonts (the primary PDF font is vendored in assets/fonts/ —
# see app/render_pdf.py). Windows paths kept for machines without the asset.
PDF_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\times.ttf",
    r"C:\Windows\Fonts\arial.ttf",
]
SOFFICE_CANDIDATES = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
]


def ensure_dirs() -> None:
    for d in (DATA_DIR, GENERATED_DIR, UPLOADS_DIR):
        d.mkdir(parents=True, exist_ok=True)
