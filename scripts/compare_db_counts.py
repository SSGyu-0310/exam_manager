"""
Compare row counts between SQLite and Postgres.

Usage:
  python scripts/compare_db_counts.py \
    --sqlite data/exam.db \
    --postgres "postgresql+psycopg://user:pass@host:5432/dbname"
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import psycopg

SKIP_TABLES = {"schema_migrations", "lecture_chunks_fts"}


def _resolve_sqlite_path(value: str) -> Path:
    if value.startswith("sqlite:///"):
        return Path(value.replace("sqlite:///", "", 1))
    if value.startswith("sqlite://"):
        return Path(value.replace("sqlite://", "", 1))
    return Path(value).resolve()


def _normalize_pg_uri(value: str) -> str:
    if value.startswith("postgresql+psycopg://"):
        return value.replace("postgresql+psycopg://", "postgresql://", 1)
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql://", 1)
    return value


def _fetch_sqlite_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return [row[0] for row in rows if row and row[0] not in SKIP_TABLES]


def _fetch_pg_tables(conn) -> set[str]:
    rows = conn.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema='public' AND table_type='BASE TABLE'
        """
    ).fetchall()
    return {row[0] for row in rows if row and row[0] not in SKIP_TABLES}


def _count_sqlite(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(row[0] if row else 0)


def _count_pg(conn, table: str) -> int:
    row = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
    return int(row[0] if row else 0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare SQLite/Postgres row counts.")
    parser.add_argument("--sqlite", required=True, help="SQLite path or URI.")
    parser.add_argument("--postgres", required=True, help="Postgres URI.")
    args = parser.parse_args()

    sqlite_path = _resolve_sqlite_path(args.sqlite)
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite DB not found: {sqlite_path}")

    sqlite_conn = sqlite3.connect(sqlite_path.as_posix())
    sqlite_conn.row_factory = sqlite3.Row
    pg_uri = _normalize_pg_uri(args.postgres)

    with psycopg.connect(pg_uri) as pg_conn:
        sqlite_tables = _fetch_sqlite_tables(sqlite_conn)
        pg_tables = _fetch_pg_tables(pg_conn)
        tables = [t for t in sqlite_tables if t in pg_tables]

        if not tables:
            print("No overlapping tables to compare.")
            return

        mismatches = 0
        for table in sorted(tables):
            sqlite_count = _count_sqlite(sqlite_conn, table)
            pg_count = _count_pg(pg_conn, table)
            status = "OK" if sqlite_count == pg_count else "DIFF"
            if status == "DIFF":
                mismatches += 1
            print(f"{table:<32} sqlite={sqlite_count:<8} postgres={pg_count:<8} {status}")

        if mismatches:
            print(f"\nMismatched tables: {mismatches}")
        else:
            print("\nAll table counts match.")

    sqlite_conn.close()


if __name__ == "__main__":
    main()
