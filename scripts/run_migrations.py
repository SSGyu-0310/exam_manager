"""
Compatibility wrapper for Postgres migrations.

Usage:
  python scripts/run_migrations.py --db "postgresql+psycopg://user:pass@host:5432/dbname"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from scripts.run_postgres_migrations import (
    DEFAULT_MIGRATIONS_DIR,
    run_migrations as run_postgres_migrations,
)


def _normalize_db_uri(db_uri: str) -> str:
    uri = db_uri.strip()
    if uri.startswith("postgres://"):
        return uri.replace("postgres://", "postgresql+psycopg://", 1)
    if uri.startswith("postgresql://"):
        return uri.replace("postgresql://", "postgresql+psycopg://", 1)
    if uri.startswith("postgresql+psycopg://"):
        return uri
    raise RuntimeError(
        "run_migrations.py now supports PostgreSQL only "
        "(postgresql+psycopg://...)."
    )


def _resolve_db_uri(db_arg: str | None) -> str:
    if db_arg:
        return _normalize_db_uri(db_arg)

    from config import get_config

    return _normalize_db_uri(str(get_config().runtime.db_uri))


def run_migrations(db_uri: str) -> int:
    return run_postgres_migrations(
        db_uri=_normalize_db_uri(db_uri),
        migrations_dir=DEFAULT_MIGRATIONS_DIR,
        dry_run=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run pending Postgres migrations.")
    parser.add_argument("--db", help="PostgreSQL URI override.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db_uri = _resolve_db_uri(args.db)
    count = run_postgres_migrations(
        db_uri=db_uri,
        migrations_dir=DEFAULT_MIGRATIONS_DIR,
        dry_run=args.dry_run,
    )
    if args.dry_run:
        print("Dry run complete.")
    else:
        print(f"Applied {count} Postgres migrations.")


if __name__ == "__main__":
    main()
