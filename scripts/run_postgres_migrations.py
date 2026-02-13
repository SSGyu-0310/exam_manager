"""
Run pending Postgres migrations in migrations/postgres.

Usage:
  python scripts/run_postgres_migrations.py --db "postgresql+psycopg://user:pass@host:5432/dbname"
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

import psycopg

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

DEFAULT_MIGRATIONS_DIR = ROOT_DIR / "migrations" / "postgres"


def _normalize_db_uri(uri: str) -> str:
    if uri.startswith("postgresql+psycopg://"):
        return uri.replace("postgresql+psycopg://", "postgresql://", 1)
    if uri.startswith("postgres://"):
        return uri.replace("postgres://", "postgresql://", 1)
    return uri


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _list_migrations(migrations_dir: Path) -> list[Path]:
    if not migrations_dir.exists():
        return []
    return sorted(
        path
        for path in migrations_dir.glob("*.sql")
        if path.is_file() and not path.name.endswith("_down.sql")
    )


def _ensure_schema_migrations(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            checksum TEXT NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def _fetch_applied(conn: psycopg.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT version, checksum FROM schema_migrations").fetchall()
    return {str(row[0]): str(row[1]) for row in rows}


def _is_begin_line(line: str) -> bool:
    return bool(re.fullmatch(r"BEGIN(?:\s+TRANSACTION)?\s*;", line.strip(), flags=re.I))


def _is_commit_line(line: str) -> bool:
    return bool(
        re.fullmatch(r"COMMIT(?:\s+TRANSACTION)?\s*;", line.strip(), flags=re.I)
    )


def _strip_outer_transaction(sql_text: str) -> str:
    lines = sql_text.splitlines()
    meaningful = [
        idx
        for idx, raw in enumerate(lines)
        if raw.strip() and not raw.strip().startswith("--")
    ]
    if len(meaningful) < 2:
        return sql_text.strip()

    commit_idx = meaningful[-1]
    if not _is_commit_line(lines[commit_idx]):
        return sql_text.strip()

    begin_idx = None
    for idx in meaningful:
        if idx >= commit_idx:
            break
        if _is_begin_line(lines[idx]):
            begin_idx = idx
    if begin_idx is None:
        return sql_text.strip()

    inner = lines[:begin_idx] + lines[begin_idx + 1 : commit_idx] + lines[commit_idx + 1 :]
    return "\n".join(inner).strip()


def _split_sql_statements(sql_text: str) -> list[str]:
    statements: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(sql_text)
    in_single = False
    in_double = False
    in_line_comment = False
    in_block_comment = False
    dollar_tag: str | None = None

    while i < n:
        ch = sql_text[i]
        nxt = sql_text[i + 1] if i + 1 < n else ""

        if in_line_comment:
            buf.append(ch)
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            buf.append(ch)
            if ch == "*" and nxt == "/":
                buf.append(nxt)
                i += 2
                in_block_comment = False
                continue
            i += 1
            continue

        if dollar_tag is not None:
            if sql_text.startswith(dollar_tag, i):
                buf.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
                continue
            buf.append(ch)
            i += 1
            continue

        if in_single:
            buf.append(ch)
            if ch == "'" and nxt == "'":
                buf.append(nxt)
                i += 2
                continue
            if ch == "'":
                in_single = False
            i += 1
            continue

        if in_double:
            buf.append(ch)
            if ch == '"':
                in_double = False
            i += 1
            continue

        if ch == "-" and nxt == "-":
            buf.append(ch)
            buf.append(nxt)
            in_line_comment = True
            i += 2
            continue

        if ch == "/" and nxt == "*":
            buf.append(ch)
            buf.append(nxt)
            in_block_comment = True
            i += 2
            continue

        if ch == "'":
            buf.append(ch)
            in_single = True
            i += 1
            continue

        if ch == '"':
            buf.append(ch)
            in_double = True
            i += 1
            continue

        if ch == "$":
            j = i + 1
            while j < n and (sql_text[j].isalnum() or sql_text[j] == "_"):
                j += 1
            if j < n and sql_text[j] == "$":
                tag = sql_text[i : j + 1]
                buf.append(tag)
                dollar_tag = tag
                i = j + 1
                continue

        if ch == ";":
            statement = "".join(buf).strip()
            if statement:
                statements.append(statement)
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def _apply_migration(
    conn: psycopg.Connection, version: str, sql_text: str, checksum: str
) -> None:
    body = _strip_outer_transaction(sql_text)
    with conn.transaction():
        for statement in _split_sql_statements(body):
            conn.execute(statement)
        conn.execute(
            "INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)",
            (version, checksum),
        )


def run_migrations(db_uri: str, migrations_dir: Path, dry_run: bool = False) -> int:
    migrations = _list_migrations(migrations_dir)
    if not migrations:
        print(f"No Postgres migrations found in: {migrations_dir}")
        return 0

    if dry_run:
        print("[DRY-RUN] Pending check only; no writes.")

    applied_count = 0
    with psycopg.connect(_normalize_db_uri(db_uri)) as conn:
        _ensure_schema_migrations(conn)
        applied = _fetch_applied(conn)

        for path in migrations:
            version = path.name
            sql_text = path.read_text(encoding="utf-8")
            checksum = _checksum(sql_text)

            if version in applied:
                if applied[version] != checksum:
                    raise RuntimeError(
                        f"Checksum mismatch for {version}: {applied[version]} != {checksum}"
                    )
                print(f"Skip: {version}")
                continue

            if dry_run:
                print(f"[DRY-RUN] Would apply: {version}")
                continue

            _apply_migration(conn, version, sql_text, checksum)
            applied_count += 1
            print(f"Applied: {version}")

    return applied_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Run pending Postgres migrations.")
    parser.add_argument("--db", default=None, help="Postgres DB URI (defaults to DATABASE_URL).")
    parser.add_argument(
        "--migrations-dir",
        default=str(DEFAULT_MIGRATIONS_DIR),
        help="Directory containing Postgres *.sql migration files.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db_uri = args.db or os.environ.get("DATABASE_URL")
    if not db_uri:
        raise RuntimeError("DATABASE_URL is required. Pass --db or set DATABASE_URL.")

    count = run_migrations(
        db_uri=db_uri,
        migrations_dir=Path(args.migrations_dir),
        dry_run=args.dry_run,
    )
    if args.dry_run:
        print("Dry run complete.")
    else:
        print(f"Applied {count} Postgres migrations.")


if __name__ == "__main__":
    main()
