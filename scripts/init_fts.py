"""
Initialize FTS resources for lecture chunks in PostgreSQL.

SAFETY: DESTRUCTIVE (if --rebuild specified)

Usage:
  python scripts/init_fts.py --db "postgresql+psycopg://user:pass@host:5432/dbname" --sync
  python scripts/init_fts.py --db "postgresql+psycopg://user:pass@host:5432/dbname" --rebuild
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))


def _normalize_db_uri(db_uri: str) -> str:
    uri = db_uri.strip()
    if uri.startswith("postgres://"):
        return uri.replace("postgres://", "postgresql+psycopg://", 1)
    if uri.startswith("postgresql://"):
        return uri.replace("postgresql://", "postgresql+psycopg://", 1)
    if uri.startswith("postgresql+psycopg://"):
        return uri
    raise RuntimeError(
        "init_fts.py supports PostgreSQL URI only (postgresql+psycopg://...)."
    )


def _resolve_db_uri(db_arg: str | None) -> str:
    if db_arg:
        return _normalize_db_uri(db_arg)

    from config import get_config

    return _normalize_db_uri(str(get_config().runtime.db_uri))


def _get_backend(db_uri: str) -> str:
    try:
        return make_url(db_uri).get_backend_name()
    except Exception:
        if db_uri.startswith("postgres"):
            return "postgresql"
        return "unknown"


def _init_fts_postgres(
    db_uri: str, rebuild: bool, sync: bool, dry_run: bool = False
) -> None:
    statements = [
        """
        ALTER TABLE lecture_chunks
        ADD COLUMN IF NOT EXISTS content_tsv tsvector
        """,
        """
        CREATE OR REPLACE FUNCTION lecture_chunks_tsv_update()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          NEW.content_tsv := to_tsvector('simple', coalesce(NEW.content, ''));
          RETURN NEW;
        END
        $$;
        """,
        """
        DROP TRIGGER IF EXISTS lecture_chunks_tsv_trigger ON lecture_chunks
        """,
        """
        CREATE TRIGGER lecture_chunks_tsv_trigger
        BEFORE INSERT OR UPDATE OF content ON lecture_chunks
        FOR EACH ROW EXECUTE FUNCTION lecture_chunks_tsv_update()
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_lecture_chunks_content_tsv
        ON lecture_chunks USING GIN (content_tsv)
        """,
    ]

    if sync or rebuild:
        statements.insert(
            1,
            """
            UPDATE lecture_chunks
            SET content_tsv = to_tsvector('simple', coalesce(content, ''))
            WHERE content_tsv IS NULL
            """,
        )

    if dry_run:
        print("[DRY-RUN] Would run the following on Postgres:")
        for stmt in statements:
            print(stmt.strip())
        return

    engine = create_engine(db_uri)
    with engine.begin() as conn:
        table_exists = conn.execute(
            text("SELECT to_regclass('public.lecture_chunks')")
        ).scalar()
        if not table_exists:
            print("lecture_chunks table not found; skipping Postgres FTS init.")
            return
        for stmt in statements:
            conn.execute(text(stmt))
    print("Postgres FTS init complete.")


def init_fts(db_uri: str, rebuild: bool, sync: bool, dry_run: bool = False) -> None:
    normalized_uri = _normalize_db_uri(db_uri)
    backend = _get_backend(normalized_uri)
    if backend not in ("postgresql", "postgres"):
        raise RuntimeError(f"Unsupported DB backend for FTS init: {backend}")
    _init_fts_postgres(normalized_uri, rebuild, sync, dry_run)


def main() -> None:
    try:
        from scripts._safety import print_script_header
    except ModuleNotFoundError:
        from _safety import print_script_header

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sync", action="store_true", help="Sync lecture_chunks into FTS."
    )
    parser.add_argument("--rebuild", action="store_true", help="Clear FTS before sync.")
    parser.add_argument("--db", help="PostgreSQL URI override.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without writing.",
    )
    parser.add_argument(
        "--yes-i-really-mean-it",
        action="store_true",
        help="Confirm destructive operation.",
    )
    args = parser.parse_args()

    resolved_db_uri = _resolve_db_uri(args.db)
    print_script_header("init_fts.py", resolved_db_uri)

    init_fts(
        resolved_db_uri,
        rebuild=args.rebuild,
        sync=args.sync or args.rebuild,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
