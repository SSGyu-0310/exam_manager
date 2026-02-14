"""
Create a Postgres backup using pg_dump.

Usage:
  python scripts/backup_postgres.py \
    --db "postgresql+psycopg://user:pass@host:5432/dbname" \
    --out backups/examdb.dump
"""
from __future__ import annotations

import argparse
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


def _normalize_db_uri(uri: str) -> str:
    if uri.startswith("postgresql+psycopg://"):
        return uri.replace("postgresql+psycopg://", "postgresql://", 1)
    if uri.startswith("postgres://"):
        return uri.replace("postgres://", "postgresql://", 1)
    return uri


def _default_out_path(uri: str) -> Path:
    parsed = urlparse(uri)
    dbname = (parsed.path or "").lstrip("/") or "postgres"
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return Path("backups") / f"{dbname}_{timestamp}.dump"


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup Postgres using pg_dump.")
    parser.add_argument("--db", required=True, help="Postgres DB URI.")
    parser.add_argument("--out", help="Output file path (.dump).")
    parser.add_argument("--schema-only", action="store_true")
    parser.add_argument("--data-only", action="store_true")
    args = parser.parse_args()

    db_uri = _normalize_db_uri(args.db)
    out_path = Path(args.out) if args.out else _default_out_path(db_uri)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "pg_dump",
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        f"--file={out_path}",
        db_uri,
    ]
    if args.schema_only:
        cmd.append("--schema-only")
    if args.data_only:
        cmd.append("--data-only")

    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)

    print(f"Backup created: {out_path}")


if __name__ == "__main__":
    main()
