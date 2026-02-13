from pathlib import Path

import pytest

from app.services import db_backup


def test_backup_database_raises_runtime_error_for_removed_sqlite_flow():
    with pytest.raises(RuntimeError, match="SQLite file backup flow has been removed"):
        db_backup.backup_database("sqlite:///:memory:", Path("backups"), 30)


def test_maybe_backup_before_write_is_noop_for_postgres(app):
    with app.app_context():
        app.config["AUTO_BACKUP_BEFORE_WRITE"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = (
            "postgresql+psycopg://u:p@localhost:5432/exam_test"
        )

        path = db_backup.maybe_backup_before_write("tests")

        assert path is None
