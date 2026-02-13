"""
Create Postgres backups with retention.

Usage:
  python scripts/backup_db.py --db "postgresql+psycopg://user:pass@host:5432/dbname" --keep 30
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))


def _normalize_db_uri(db_uri: str) -> str:
    uri = db_uri.strip()
    if uri.startswith("postgres://"):
        return uri.replace("postgres://", "postgresql://", 1)
    if uri.startswith("postgresql+psycopg://"):
        return uri.replace("postgresql+psycopg://", "postgresql://", 1)
    if uri.startswith("postgresql://"):
        return uri
    raise RuntimeError(
        "backup_db.py now supports PostgreSQL only (postgresql+psycopg://...)."
    )


def _resolve_db_uri(db_arg: str | None) -> str:
    if db_arg:
        return _normalize_db_uri(db_arg)

    from config import get_config

    return _normalize_db_uri(str(get_config().runtime.db_uri))


def _db_name(db_uri: str) -> str:
    parsed = urlparse(db_uri)
    name = (parsed.path or "").lstrip("/")
    if not name:
        raise RuntimeError("Database name is missing in DB URI.")
    return name


def _backup_path(db_name: str, backup_dir: Path) -> Path:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return backup_dir / f"{db_name}_{timestamp}.dump"


def _prune_backups(backup_dir: Path, db_name: str, keep: int) -> int:
    if keep <= 0:
        return 0
    backups = sorted(backup_dir.glob(f"{db_name}_*.dump"))
    if len(backups) <= keep:
        return 0
    removed = 0
    for path in backups[: len(backups) - keep]:
        path.unlink(missing_ok=True)
        removed += 1
    return removed


def backup_database(
    db_uri: str,
    backup_dir: Path,
    keep: int,
    schema_only: bool = False,
    data_only: bool = False,
) -> Path:
    normalized_uri = _normalize_db_uri(db_uri)
    db_name = _db_name(normalized_uri)
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = _backup_path(db_name, backup_dir)

    cmd = [
        "pg_dump",
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        f"--file={backup_path}",
        normalized_uri,
    ]
    if schema_only:
        cmd.append("--schema-only")
    if data_only:
        cmd.append("--data-only")

    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)

    _prune_backups(backup_dir, db_name, keep)
    return backup_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup PostgreSQL with retention.")
    parser.add_argument("--db", help="PostgreSQL URI override.")
    parser.add_argument("--keep", type=int, default=30, help="Keep latest N backups.")
    parser.add_argument(
        "--backup-dir",
        default=str(ROOT_DIR / "backups"),
        help="Directory to store backups.",
    )
    parser.add_argument("--schema-only", action="store_true")
    parser.add_argument("--data-only", action="store_true")
    args = parser.parse_args()

    db_uri = _resolve_db_uri(args.db)
    backup_path = backup_database(
        db_uri=db_uri,
        backup_dir=Path(args.backup_dir),
        keep=args.keep,
        schema_only=args.schema_only,
        data_only=args.data_only,
    )
    print(f"Backup created: {backup_path}")


if __name__ == "__main__":
    main()
