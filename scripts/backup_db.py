"""
Hot backup for SQLite databases.

Usage:
  python scripts/backup_db.py --db path/to/exam.db --keep 30
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))


def _resolve_db_uri(db_arg: str | None) -> str:
    if db_arg:
        if "://" in db_arg:
            return db_arg
        return f"sqlite:///{Path(db_arg).resolve()}"

    from config import get_config

    return str(get_config().runtime.db_uri)


def _sqlite_path_from_uri(uri: str) -> Path:
    if uri.startswith("sqlite:///"):
        return Path(uri.replace("sqlite:///", "", 1))
    if uri.startswith("sqlite://"):
        return Path(uri.replace("sqlite://", "", 1))
    raise RuntimeError("backup_db.py only supports SQLite databases.")


def _backup_path(db_path: Path, backup_dir: Path) -> Path:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return backup_dir / f"{db_path.name}.{timestamp}"


def _prune_backups(backup_dir: Path, db_name: str, keep: int) -> int:
    if keep <= 0:
        return 0
    pattern = f"{db_name}.*"
    backups = sorted(backup_dir.glob(pattern))
    if len(backups) <= keep:
        return 0
    removed = 0
    for path in backups[: len(backups) - keep]:
        path.unlink(missing_ok=True)
        removed += 1
    return removed


def hot_backup(db_path: Path, backup_dir: Path, keep: int) -> Path:
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite DB not found: {db_path}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = _backup_path(db_path, backup_dir)

    with sqlite3.connect(db_path.as_posix()) as src, sqlite3.connect(
        backup_path.as_posix()
    ) as dst:
        src.backup(dst)

    _prune_backups(backup_dir, db_path.name, keep)
    return backup_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Hot backup a SQLite database.")
    parser.add_argument("--db", help="Path to sqlite db file.")
    parser.add_argument("--keep", type=int, default=30, help="Keep latest N backups.")
    parser.add_argument(
        "--backup-dir",
        default=str(ROOT_DIR / "backups"),
        help="Directory to store backups.",
    )
    args = parser.parse_args()

    db_uri = _resolve_db_uri(args.db)
    db_path = _sqlite_path_from_uri(db_uri)
    backup_dir = Path(args.backup_dir)
    backup_path = hot_backup(db_path, backup_dir, args.keep)
    print(f"Backup created: {backup_path}")


if __name__ == "__main__":
    main()
