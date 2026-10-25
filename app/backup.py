"""Backups (PLANS.md §9 Phase 6): zip the data directory (SQLite via the online
backup API for consistency, plus generated files, uploads and the encryption key)
into data/backups/, keeping the 10 newest. CLI:

    python -m app.backup
"""
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path

from . import config, db

KEEP = 10


def create_backup() -> Path:
    config.ensure_dirs()
    backups_dir = config.DATA_DIR / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    out_path = backups_dir / f"backup_{stamp}.zip"

    # Consistent snapshot of the live database.
    snapshot = backups_dir / f"app_{stamp}.db"
    source = db.get_conn()
    dest = sqlite3.connect(str(snapshot))
    with dest:
        source.backup(dest)
    dest.close()

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(snapshot, "app.db")
        snapshot.unlink(missing_ok=True)
        for folder in ("generated", "uploads"):
            base = config.DATA_DIR / folder
            if not base.exists():
                continue
            for path in sorted(base.rglob("*")):
                if path.is_file():
                    zf.write(path, f"{folder}/{path.relative_to(base)}")
        key_file = config.DATA_DIR / "secret.key"
        if key_file.exists():
            zf.write(key_file, "secret.key")

    old = sorted(backups_dir.glob("backup_*.zip"))
    for stale in old[:-KEEP]:
        stale.unlink(missing_ok=True)
    return out_path


if __name__ == "__main__":
    print(f"Đã sao lưu vào: {create_backup()}")
