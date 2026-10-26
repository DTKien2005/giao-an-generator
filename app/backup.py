"""Backups (PLANS_V6.md WP4): zip the data directory (SQLite via the online
backup API for consistency, plus generated files, uploads and the encryption key)
into data/backups/, keeping the 10 newest; optionally copy the finished zip to
APP_BACKUP_COPY_DIR (off-disk). The local zip is atomic (written as `.part`,
integrity-checked, then renamed) and a failed copy never corrupts it — the CLI
exits non-zero instead. CLI:

    python -m app.backup
"""
import os
import sqlite3
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from . import config, db

KEEP = 10


def _copy_off_disk(zip_path: Path) -> Path:
    """Copy the finished zip to APP_BACKUP_COPY_DIR and verify by size."""
    dest_dir = Path(config.BACKUP_COPY_DIR)
    resolved = dest_dir.resolve()
    data_root = config.DATA_DIR.resolve()
    if data_root == resolved or data_root in resolved.parents:
        raise ValueError("APP_BACKUP_COPY_DIR không được nằm bên trong thư mục data/")
    if not dest_dir.is_dir():
        raise FileNotFoundError(f"Thư mục copy không tồn tại: {dest_dir}")
    dest = dest_dir / zip_path.name
    tmp = dest_dir / (zip_path.name + ".part")
    try:
        data = zip_path.read_bytes()
        tmp.write_bytes(data)
        if tmp.stat().st_size != len(data):
            raise OSError("Bản copy không khớp kích thước với bản gốc")
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)
    return dest


def create_backup() -> tuple[Path, Path | None]:
    """Create the local zip atomically; copy off-disk when configured.

    Returns (local_zip, copied_to_or_None). Raises on local-zip failure; the
    caller decides how a copy failure is surfaced (CLI → non-zero exit).
    """
    config.ensure_dirs()
    backups_dir = config.DATA_DIR / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    final_path = backups_dir / f"backup_{stamp}.zip"
    part_path = backups_dir / f"backup_{stamp}.zip.part"

    # Consistent snapshot of the live database.
    snapshot = backups_dir / f"app_{stamp}.db"
    source = db.get_conn()
    dest = sqlite3.connect(str(snapshot))
    with dest:
        source.backup(dest)
    dest.close()

    try:
        with zipfile.ZipFile(part_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(snapshot, "app.db")
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
        # Integrity gate before the atomic rename (Codex R1-18).
        with zipfile.ZipFile(part_path) as zf:
            if zf.testzip() is not None or "app.db" not in zf.namelist():
                raise OSError("Tệp zip không qua kiểm tra toàn vẹn")
        os.replace(part_path, final_path)
    finally:
        part_path.unlink(missing_ok=True)
        snapshot.unlink(missing_ok=True)

    old = sorted(backups_dir.glob("backup_*.zip"))
    for stale in old[:-KEEP]:
        stale.unlink(missing_ok=True)

    copied_to = None
    if config.BACKUP_COPY_DIR:
        copied_to = _copy_off_disk(final_path)
    return final_path, copied_to


def main() -> int:
    try:
        zip_path, copied_to = create_backup()
    except Exception as exc:
        print(f"LỖI sao lưu: {exc}", file=sys.stderr)
        return 1
    print(f"Đã sao lưu vào: {zip_path}")
    if copied_to:
        print(f"Đã copy ra ngoài đĩa: {copied_to}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
