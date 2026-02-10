from __future__ import annotations

from sqlalchemy import inspect, text

from app import db


def ensure_question_examiner_column(logger=None) -> None:
    """Ensure `questions.examiner` column exists across SQLite/Postgres.

    This keeps existing deployed databases (especially Docker Postgres volumes)
    compatible with the updated Question model without manual intervention.
    """
    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())
    if "questions" not in table_names:
        return

    column_names = {col.get("name") for col in inspector.get_columns("questions")}
    if "examiner" in column_names:
        return

    db.session.execute(text("ALTER TABLE questions ADD COLUMN examiner VARCHAR(120)"))
    db.session.commit()
    if logger:
        logger.warning("Applied schema patch: added questions.examiner column.")
