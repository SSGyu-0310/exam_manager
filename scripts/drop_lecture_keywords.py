"""
Deprecated compatibility stub.

Schema changes must be applied through Postgres migrations in `migrations/postgres/`.
"""
from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deprecated: use migrations/postgres for schema changes."
    )
    parser.add_argument("--db", help="Deprecated.")
    parser.add_argument("--no-backup", action="store_true", help="Deprecated.")
    parser.add_argument("--dry-run", action="store_true", help="Deprecated.")
    parser.add_argument(
        "--yes-i-really-mean-it",
        action="store_true",
        help="Deprecated.",
    )
    parser.parse_args()
    raise RuntimeError(
        "scripts/drop_lecture_keywords.py is deprecated in PostgreSQL-only mode. "
        "Use a SQL migration under migrations/postgres/."
    )


if __name__ == "__main__":
    main()
