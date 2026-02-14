from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app import db


def _is_duplicate_column_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    if "duplicate column" in msg or "already exists" in msg:
        return True
    # PostgreSQL duplicate_column SQLSTATE
    if "42701" in msg:
        return True
    orig = getattr(exc, "orig", None)
    if orig is not None:
        omsg = str(orig).lower()
        if "duplicate column" in omsg or "already exists" in omsg or "42701" in omsg:
            return True
    return False


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

    try:
        db.session.execute(text("ALTER TABLE questions ADD COLUMN examiner VARCHAR(120)"))
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        if _is_duplicate_column_error(exc):
            if logger:
                logger.info("Schema patch skipped: questions.examiner already exists.")
            return
        raise
    if logger:
        logger.warning("Applied schema patch: added questions.examiner column.")


def ensure_question_ai_final_lecture_column(logger=None) -> None:
    """Ensure `questions.ai_final_lecture_id` exists across SQLite/Postgres."""
    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())
    if "questions" not in table_names:
        return

    column_names = {col.get("name") for col in inspector.get_columns("questions")}
    if "ai_final_lecture_id" in column_names:
        return

    try:
        db.session.execute(
            text("ALTER TABLE questions ADD COLUMN ai_final_lecture_id INTEGER")
        )
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        if _is_duplicate_column_error(exc):
            if logger:
                logger.info(
                    "Schema patch skipped: questions.ai_final_lecture_id already exists."
                )
            return
        raise
    if logger:
        logger.warning("Applied schema patch: added questions.ai_final_lecture_id column.")
