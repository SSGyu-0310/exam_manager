"""
Initialize FTS resources for lecture chunks (SQLite FTS5 or Postgres tsvector).

SAFETY: DESTRUCTIVE (if --rebuild specified)

Usage:
  python scripts/init_fts.py --sync
  python scripts/init_fts.py --rebuild
  python scripts/init_fts.py --db path/to/exam.db --rebuild
  python scripts/init_fts.py --db postgresql+psycopg://user:pass@host:5432/dbname --sync
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

# Removed: from config import Config (now using config package)


def _resolve_db_uri(db_arg: str | None) -> str:
    if db_arg:
        if "://" in db_arg:
            return db_arg
        return f"sqlite:///{Path(db_arg).resolve()}"

    from config import get_config

    return get_config().runtime.db_uri


def _get_backend(db_uri: str) -> str:
    try:
        return make_url(db_uri).get_backend_name()
    except Exception:
        if db_uri.startswith("sqlite"):
            return "sqlite"
        if db_uri.startswith("postgres"):
            return "postgresql"
        return "unknown"


def _sqlite_path_from_uri(db_uri: str) -> str:
    if db_uri.startswith("sqlite:///"):
        return db_uri.replace("sqlite:///", "", 1)
    if db_uri.startswith("sqlite://"):
        return db_uri.replace("sqlite://", "", 1)
    return db_uri


def _table_exists(cursor: sqlite3.Cursor, name: str) -> bool:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (name,),
    )
    return cursor.fetchone() is not None


def _init_fts_sqlite(
    db_path: str, rebuild: bool, sync: bool, dry_run: bool = False
) -> None:
    db_path = os.path.abspath(db_path)
    if not os.path.exists(db_path):
        raise RuntimeError(f"SQLite DB not found: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS lecture_chunks_fts
        USING fts5(
            content,
            chunk_id UNINDEXED,
            lecture_id UNINDEXED,
            page_start UNINDEXED,
            page_end UNINDEXED
        )
        """
    )

    if rebuild:
        cursor.execute("DELETE FROM lecture_chunks_fts")

    if sync:
        if not _table_exists(cursor, "lecture_chunks"):
            print("lecture_chunks table not found; skipping sync.")
        else:
            cursor.execute(
                "SELECT id, lecture_id, page_start, page_end, content FROM lecture_chunks"
            )
            rows = cursor.fetchall()
            if not dry_run:
                cursor.executemany(
                    """
                    INSERT INTO lecture_chunks_fts
                        (content, chunk_id, lecture_id, page_start, page_end)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (content, chunk_id, lecture_id, page_start, page_end)
                        for chunk_id, lecture_id, page_start, page_end, content in rows
                    ],
                )
                print(f"Synchronized {len(rows)} chunks into FTS.")
            else:
                print(f"[DRY-RUN] Would synchronize {len(rows)} chunks into FTS.")

    if not dry_run:
        conn.commit()
        conn.close()
        print("FTS init complete.")
    else:
        print("[DRY-RUN] Skipping commit and close")


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
    backend = _get_backend(db_uri)
    if backend == "sqlite":
        _init_fts_sqlite(_sqlite_path_from_uri(db_uri), rebuild, sync, dry_run)
        return
    if backend in ("postgresql", "postgres"):
        _init_fts_postgres(db_uri, rebuild, sync, dry_run)
        return
    raise RuntimeError(f"Unsupported DB backend for FTS init: {backend}")


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
    parser.add_argument("--db", help="Path to sqlite db file.")
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

    print_script_header("init_fts.py", _resolve_db_uri(args.db))

    init_fts(
        _resolve_db_uri(args.db),
        rebuild=args.rebuild,
        sync=args.sync or args.rebuild,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
