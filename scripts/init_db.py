"""
Initialize database schema via SQLAlchemy models.

Usage:
  python scripts/init_db.py --db postgresql+psycopg://user:pass@host:5432/dbname
"""
from __future__ import annotations

import argparse
import sys

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from app import create_app, db


def _normalize_db_uri(db_value: str | None) -> str | None:
    if not db_value:
        return None
    db_uri = db_value.strip()
    if db_uri.startswith("postgres://"):
        db_uri = db_uri.replace("postgres://", "postgresql+psycopg://", 1)
    elif db_uri.startswith("postgresql://"):
        db_uri = db_uri.replace("postgresql://", "postgresql+psycopg://", 1)
    if not db_uri.startswith("postgresql+psycopg://"):
        raise RuntimeError(
            "--db must be a PostgreSQL URI (postgresql+psycopg://...). "
            "Non-PostgreSQL DB path/URI is no longer supported."
        )
    return db_uri


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize PostgreSQL schema.")
    parser.add_argument(
        "--db",
        help="PostgreSQL URI override (postgresql+psycopg://...).",
    )
    parser.add_argument(
        "--config",
        default="default",
        help="Config name: development|production|local_admin|default",
    )
    args = parser.parse_args()

    db_uri = _normalize_db_uri(args.db)
    app = create_app(
        args.config,
        db_uri_override=db_uri,
        skip_migration_check=True,
    )
    with app.app_context():
        db.create_all()
    print("Schema initialized.")


if __name__ == "__main__":
    main()
