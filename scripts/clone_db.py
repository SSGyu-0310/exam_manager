"""
Legacy compatibility stub.

Legacy file cloning has been removed as part of the PostgreSQL-only migration.
Use Postgres-native backup/restore or managed snapshots instead.
"""
from __future__ import annotations

import argparse


def clone_db(*_args, **_kwargs) -> None:
    raise RuntimeError(
        "scripts/clone_db.py is no longer supported in PostgreSQL-only mode. "
        "Use pg_dump/pg_restore (or infrastructure snapshot tooling)."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deprecated: legacy clone flow has been removed."
    )
    parser.add_argument("--db", help="Deprecated.")
    parser.add_argument("--out", help="Deprecated.")
    parser.parse_args()
    clone_db()


if __name__ == "__main__":
    main()
