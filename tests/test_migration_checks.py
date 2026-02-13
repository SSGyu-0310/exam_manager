from __future__ import annotations

from pathlib import Path

import pytest

from app.services import migrations as migration_service


class _CaptureLogger:
    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.infos: list[str] = []

    def warning(self, message: str, *args) -> None:
        self.warnings.append(message % args if args else message)

    def info(self, message: str, *args) -> None:
        self.infos.append(message % args if args else message)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_detect_pending_migrations_postgres_ignores_down_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    migrations_dir = tmp_path / "migrations"
    up = migrations_dir / "postgres" / "20260210_1600_search_fts.sql"
    down = migrations_dir / "postgres" / "20260210_1600_search_fts_down.sql"
    _write(up, "SELECT 1;")
    _write(down, "SELECT 2;")

    monkeypatch.setattr(
        migration_service, "_fetch_applied_postgres", lambda _db_uri: ({}, True)
    )

    pending, mismatched = migration_service.detect_pending_migrations(
        "postgresql+psycopg://u:p@localhost:5432/dbname", migrations_dir
    )

    assert pending == [up.name]
    assert mismatched == []


def test_detect_pending_migrations_postgres_reports_checksum_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    migrations_dir = tmp_path / "migrations"
    up = migrations_dir / "postgres" / "20260210_1600_search_fts.sql"
    _write(up, "SELECT 1;")

    monkeypatch.setattr(
        migration_service,
        "_fetch_applied_postgres",
        lambda _db_uri: ({up.name: "invalid-checksum"}, True),
    )

    pending, mismatched = migration_service.detect_pending_migrations(
        "postgresql+psycopg://u:p@localhost:5432/dbname", migrations_dir
    )

    assert pending == []
    assert mismatched == [up.name]


def test_check_pending_migrations_postgres_warns_without_tracking_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    migrations_dir = tmp_path / "migrations"
    up = migrations_dir / "postgres" / "20260210_1600_search_fts.sql"
    _write(up, "SELECT 1;")

    logger = _CaptureLogger()
    monkeypatch.setattr(
        migration_service, "_fetch_applied_postgres", lambda _db_uri: ({}, False)
    )

    migration_service.check_pending_migrations(
        db_uri="postgresql+psycopg://u:p@localhost:5432/dbname",
        migrations_dir=migrations_dir,
        env_name="development",
        logger=logger,
        fail_on_pending=False,
    )

    assert any("schema_migrations table not found" in msg for msg in logger.warnings)
    assert any("Pending migrations detected" in msg for msg in logger.warnings)


def test_check_pending_migrations_postgres_raises_in_production_on_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    migrations_dir = tmp_path / "migrations"
    up = migrations_dir / "postgres" / "20260210_1600_search_fts.sql"
    _write(up, "SELECT 1;")

    logger = _CaptureLogger()
    monkeypatch.setattr(
        migration_service, "_fetch_applied_postgres", lambda _db_uri: ({}, True)
    )

    with pytest.raises(RuntimeError, match="Pending or mismatched migrations"):
        migration_service.check_pending_migrations(
            db_uri="postgresql+psycopg://u:p@localhost:5432/dbname",
            migrations_dir=migrations_dir,
            env_name="production",
            logger=logger,
            fail_on_pending=True,
        )


def test_detect_pending_migrations_skips_non_postgres_uri(tmp_path: Path) -> None:
    pending, mismatched = migration_service.detect_pending_migrations(
        "mysql://u:p@localhost:3306/exam",
        tmp_path / "migrations",
    )
    assert pending == []
    assert mismatched == []
