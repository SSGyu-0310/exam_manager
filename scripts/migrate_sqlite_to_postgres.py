"""
Migrate data from SQLite to Postgres using SQLAlchemy.

Usage:
  python scripts/migrate_sqlite_to_postgres.py \
    --sqlite data/exam.db \
    --postgres "postgresql+psycopg://user:pass@host:5432/dbname"
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Iterable, Dict, Any, List

from sqlalchemy import Boolean, create_engine, inspect, MetaData, Table, text

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

SKIP_TABLES = {"schema_migrations", "lecture_chunks_fts"}


def _resolve_sqlite_uri(value: str) -> str:
    if value.startswith("sqlite://"):
        return value
    return f"sqlite:///{Path(value).resolve()}"


def _resolve_postgres_uri(value: str) -> str:
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


def _sqlite_path_from_uri(uri: str) -> Path:
    if uri.startswith("sqlite:///"):
        return Path(uri.replace("sqlite:///", "", 1))
    if uri.startswith("sqlite://"):
        return Path(uri.replace("sqlite://", "", 1))
    raise RuntimeError("Invalid SQLite URI")


def _fetch_sqlite_tables(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return [row[0] for row in rows if row and row[0]]


def _topological_table_order(tables: Iterable[str], inspector) -> List[str]:
    tables = list(tables)
    deps: Dict[str, set[str]] = {t: set() for t in tables}
    for table in tables:
        for fk in inspector.get_foreign_keys(table):
            ref = fk.get("referred_table")
            if ref and ref in deps and ref != table:
                deps[table].add(ref)

    ordered: List[str] = []
    pending = set(tables)
    while pending:
        ready = sorted([t for t in pending if deps[t].issubset(set(ordered))])
        if not ready:
            # Cycle or unresolved dependency; fall back to alphabetical.
            ready = sorted(pending)
        for table in ready:
            ordered.append(table)
            pending.remove(table)
    return ordered


def _select_sqlite_rows(
    conn: sqlite3.Connection, table: str, chunk_size: int
) -> Iterable[List[sqlite3.Row]]:
    order_clause = ""
    if table == "block_folders":
        order_clause = " ORDER BY parent_id IS NOT NULL, parent_id, id"
    cursor = conn.execute(f"SELECT * FROM {table}{order_clause}")
    while True:
        rows = cursor.fetchmany(chunk_size)
        if not rows:
            break
        yield rows


def _copy_table(
    *,
    sqlite_conn: sqlite3.Connection,
    pg_conn,
    pg_table: Table,
    table_name: str,
    chunk_size: int,
    dry_run: bool,
) -> int:
    total = 0
    for rows in _select_sqlite_rows(sqlite_conn, table_name, chunk_size):
        payload = [_coerce_row(dict(row), pg_table) for row in rows]
        total += len(payload)
        if not dry_run and payload:
            pg_conn.execute(pg_table.insert(), payload)
    return total


def _coerce_row(row: Dict[str, Any], pg_table: Table) -> Dict[str, Any]:
    for col in pg_table.columns:
        if col.name not in row:
            continue
        value = row[col.name]
        if value is None:
            continue
        if isinstance(value, str):
            if "\0" in value:
                value = value.replace("\0", "")
                row[col.name] = value

        if isinstance(col.type, Boolean):
            if isinstance(value, (int, float)):
                row[col.name] = bool(value)
            elif isinstance(value, str):
                lowered = value.lower()
                if lowered in ("0", "1"):
                    row[col.name] = lowered == "1"
                elif lowered in ("t", "true", "f", "false"):
                    row[col.name] = lowered in ("t", "true")
    return row


def _reset_sequences(pg_conn, tables: Iterable[str]) -> None:
    for table in tables:
        try:
            seq = pg_conn.execute(
                text("SELECT pg_get_serial_sequence(:table, 'id')"),
                {"table": table},
            ).scalar()
        except Exception:
            # Table might not have 'id' column
            continue
            
        if not seq:
            continue
        max_id = pg_conn.execute(text(f"SELECT MAX(id) FROM {table}")).scalar() or 0
        if max_id > 0:
            pg_conn.execute(text("SELECT setval(:seq, :val, true)"), {"seq": seq, "val": max_id})


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate SQLite data to Postgres.")
    parser.add_argument("--sqlite", required=True, help="SQLite DB path or URI.")
    parser.add_argument("--postgres", required=True, help="Postgres URI.")
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--no-truncate", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sqlite_uri = _resolve_sqlite_uri(args.sqlite)
    postgres_uri = _resolve_postgres_uri(args.postgres)

    sqlite_path = _sqlite_path_from_uri(sqlite_uri)
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite DB not found: {sqlite_path}")

    sqlite_conn = sqlite3.connect(sqlite_path.as_posix())
    sqlite_conn.row_factory = sqlite3.Row

    print(f"DEBUG: Connecting to Postgres: {postgres_uri}")
    pg_engine = create_engine(postgres_uri, isolation_level="AUTOCOMMIT")
    inspector = inspect(pg_engine)
    pg_tables = set(inspector.get_table_names())

    sqlite_tables = _fetch_sqlite_tables(sqlite_conn)
    tables = [
        t for t in sqlite_tables if t in pg_tables and t not in SKIP_TABLES
    ]
    if not tables:
        print("No tables to migrate.")
        return

    ordered = _topological_table_order(tables, inspector)

    metadata = MetaData()
    print(f"Tables to migrate ({len(ordered)}): {', '.join(ordered)}")
    
    # Use explicit transaction management via raw SQL on AUTOCOMMIT connection
    with pg_engine.connect() as pg_conn:
        # print("Starting transaction...")
        # pg_conn.execute(text("BEGIN"))
        
        for table in ordered:
            # print(f"Processing {table}...")
            pg_table = Table(table, metadata, autoload_with=pg_conn)
            if not args.no_truncate and not args.dry_run:
                pg_conn.execute(
                    text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
                )
            count = _copy_table(
                sqlite_conn=sqlite_conn,
                pg_conn=pg_conn,
                pg_table=pg_table,
                table_name=table,
                chunk_size=args.chunk_size,
                dry_run=args.dry_run,
            )
            print(f"  {table}: {count} rows")

        if not args.dry_run:
            _reset_sequences(pg_conn, ordered)
        
        pg_conn.execute(text("COMMIT"))
        print("Transaction committed successfully.")

    sqlite_conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    main()
