from __future__ import annotations

from pathlib import Path

from flask import current_app


def backup_database(db_uri: str, backup_dir: Path, keep: int) -> Path:
    raise RuntimeError(
        "In-app SQLite file backup flow has been removed. "
        "Use external Postgres backup tooling (e.g., pg_dump/snapshot policy)."
    )


def maybe_backup_before_write(action: str | None = None) -> Path | None:
    config = current_app.config
    if not config.get("AUTO_BACKUP_BEFORE_WRITE", False):
        return None

    db_uri = config.get("SQLALCHEMY_DATABASE_URI")
    if not db_uri:
        return None

    current_app.logger.info(
        "Skipping in-app DB backup before write%s for DB %s. "
        "Use external Postgres backup policy.",
        f" ({action})" if action else "",
        db_uri,
    )
    return None
