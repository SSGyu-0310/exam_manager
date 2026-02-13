from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List, Tuple

from sqlalchemy import create_engine, text


def _is_postgres_uri(db_uri: str) -> bool:
    lowered = db_uri.lower()
    return lowered.startswith("postgresql://") or lowered.startswith(
        "postgresql+psycopg://"
    ) or lowered.startswith("postgres://")


def _load_postgres_migrations(migrations_dir: Path) -> List[Path]:
    postgres_dir = migrations_dir / "postgres"
    if not postgres_dir.exists():
        return []
    return sorted(
        path
        for path in postgres_dir.glob("*.sql")
        if path.is_file() and not path.name.endswith("_down.sql")
    )


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fetch_applied_postgres(db_uri: str) -> tuple[Dict[str, str], bool]:
    engine = create_engine(db_uri, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            has_tracking_table = bool(
                conn.execute(
                    text("SELECT to_regclass('public.schema_migrations') IS NOT NULL")
                ).scalar()
            )
            if not has_tracking_table:
                return {}, False
            rows = conn.execute(
                text("SELECT version, checksum FROM schema_migrations")
            ).fetchall()
            return {str(row[0]): str(row[1]) for row in rows}, True
    finally:
        engine.dispose()


def _detect_pending_from_applied(
    migrations: List[Path], applied: Dict[str, str]
) -> Tuple[List[str], List[str]]:
    pending = []
    mismatched = []
    for path in migrations:
        version = path.name
        sql_text = path.read_text(encoding="utf-8")
        checksum = _checksum(sql_text)
        if version not in applied:
            pending.append(version)
            continue
        if applied[version] != checksum:
            mismatched.append(version)
    return pending, mismatched


def _detect_pending_migrations_postgres(
    db_uri: str, migrations_dir: Path
) -> Tuple[List[str], List[str], bool]:
    migrations = _load_postgres_migrations(migrations_dir)
    if not migrations:
        return [], [], True

    applied, has_tracking_table = _fetch_applied_postgres(db_uri)
    pending, mismatched = _detect_pending_from_applied(migrations, applied)
    return pending, mismatched, has_tracking_table


def detect_pending_migrations(
    db_uri: str, migrations_dir: Path
) -> Tuple[List[str], List[str]]:
    if not _is_postgres_uri(db_uri):
        return [], []
    pending, mismatched, _ = _detect_pending_migrations_postgres(
        db_uri, migrations_dir
    )
    return pending, mismatched


def check_pending_migrations(
    db_uri: str,
    migrations_dir: Path,
    env_name: str,
    logger,
    fail_on_pending: bool,
) -> None:
    if not _is_postgres_uri(db_uri):
        logger.info("Unsupported DB URI for migration check; skipping.")
        return

    pending, mismatched, has_tracking_table = _detect_pending_migrations_postgres(
        db_uri, migrations_dir
    )
    if not has_tracking_table and (pending or mismatched):
        logger.warning(
            "Postgres schema_migrations table not found; "
            "treating Postgres migrations as pending."
        )

    if not pending and not mismatched:
        return

    if pending:
        logger.warning("Pending migrations detected: %s", ", ".join(pending))
    if mismatched:
        logger.warning(
            "Migration checksum mismatch detected: %s", ", ".join(mismatched)
        )

    if env_name == "production" and fail_on_pending:
        raise RuntimeError("Pending or mismatched migrations detected in production.")
