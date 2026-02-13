"""
Verify Postgres setup (FTS trigger/index, pg_stat_statements).

Usage:
  python scripts/verify_postgres_setup.py \
    --db "postgresql+psycopg://user:pass@host:5432/dbname"
"""
from __future__ import annotations

import argparse

from dotenv import load_dotenv

import psycopg


def _normalize_db_uri(uri: str) -> str:
    if uri.startswith("postgresql+psycopg://"):
        return uri.replace("postgresql+psycopg://", "postgresql://", 1)
    if uri.startswith("postgres://"):
        return uri.replace("postgres://", "postgresql://", 1)
    return uri


def _fetch_scalar(conn, sql: str, params: dict | None = None):
    row = conn.execute(sql, params or {}).fetchone()
    return row[0] if row else None


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Verify Postgres setup.")
    parser.add_argument("--db", required=True, help="Postgres DB URI.")
    args = parser.parse_args()

    db_uri = _normalize_db_uri(args.db)

    checks = []
    with psycopg.connect(db_uri) as conn:
        checks.append(("lecture_chunks table", _fetch_scalar(
            conn,
            "SELECT to_regclass('public.lecture_chunks') IS NOT NULL",
        )))
        checks.append(("content_tsv column", _fetch_scalar(
            conn,
            """
            SELECT EXISTS (
              SELECT 1
              FROM information_schema.columns
              WHERE table_schema='public'
                AND table_name='lecture_chunks'
                AND column_name='content_tsv'
            )
            """,
        )))
        checks.append(("FTS trigger", _fetch_scalar(
            conn,
            """
            SELECT EXISTS (
              SELECT 1
              FROM pg_trigger t
              JOIN pg_class c ON c.oid = t.tgrelid
              WHERE c.relname = 'lecture_chunks'
                AND t.tgname = 'lecture_chunks_tsv_trigger'
                AND NOT t.tgisinternal
            )
            """,
        )))
        checks.append(("FTS GIN index", _fetch_scalar(
            conn,
            """
            SELECT EXISTS (
              SELECT 1
              FROM pg_indexes
              WHERE schemaname='public'
                AND tablename='lecture_chunks'
                AND indexname='idx_lecture_chunks_content_tsv'
            )
            """,
        )))
        checks.append(("pg_trgm extension", _fetch_scalar(
            conn,
            "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='pg_trgm')",
        )))
        checks.append(("Trigram GIN index", _fetch_scalar(
            conn,
            """
            SELECT EXISTS (
              SELECT 1
              FROM pg_indexes
              WHERE schemaname='public'
                AND tablename='lecture_chunks'
                AND indexname='idx_lecture_chunks_content_trgm'
            )
            """,
        )))

        try:
            preload = _fetch_scalar(conn, "SHOW shared_preload_libraries")
            has_preload = bool(preload and "pg_stat_statements" in preload)
        except psycopg.errors.InsufficientPrivilege:
            conn.rollback()
            has_preload = "SKIPPED (no permission)"
        
        checks.append(("shared_preload_libraries has pg_stat_statements", has_preload))

        ext_installed = _fetch_scalar(
            conn,
            "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='pg_stat_statements')",
        )
        checks.append(("pg_stat_statements extension", ext_installed))

        stat_view_ok = False
        try:
            conn.execute("SELECT 1 FROM pg_stat_statements LIMIT 1")
            stat_view_ok = True
        except Exception:
            stat_view_ok = False
        checks.append(("pg_stat_statements view queryable", stat_view_ok))

    failed = 0
    for label, ok in checks:
        if isinstance(ok, str):
            status = ok
        else:
            status = "OK" if ok else "MISSING"
        
        if ok is False:
            failed += 1
        print(f"{label:<45} {status}")

    if failed:
        print("\nSome checks failed. See below for guidance:")
        if not any(label == "shared_preload_libraries has pg_stat_statements" and ok for label, ok in checks):
            print("- Add pg_stat_statements to shared_preload_libraries and restart Postgres.")
        if not any(label == "pg_stat_statements extension" and ok for label, ok in checks):
            print("- Run: CREATE EXTENSION IF NOT EXISTS pg_stat_statements;")
    else:
        print("\nAll checks passed.")


if __name__ == "__main__":
    main()
