"""
Apply performance indexes on Postgres.

Usage:
  python scripts/apply_postgres_indexes.py \
    --db "postgresql+psycopg://user:pass@host:5432/dbname"
"""
from __future__ import annotations

import argparse
from typing import List

from sqlalchemy import create_engine, text


def _normalize_db_uri(uri: str) -> str:
    if uri.startswith("postgres://"):
        return uri.replace("postgres://", "postgresql+psycopg://", 1)
    if uri.startswith("postgresql://"):
        return uri.replace("postgresql://", "postgresql+psycopg://", 1)
    return uri


def _index_statements() -> List[str]:
    return [
        # Questions: exam ordering + lecture filter + classified counts
        "CREATE INDEX IF NOT EXISTS idx_questions_exam_qnum ON questions (exam_id, question_number)",
        "CREATE INDEX IF NOT EXISTS idx_questions_lecture_id ON questions (lecture_id)",
        "CREATE INDEX IF NOT EXISTS idx_questions_user_classified ON questions (user_id, is_classified)",
        # Choices / notes
        "CREATE INDEX IF NOT EXISTS idx_choices_question_id ON choices (question_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_notes_question_id ON user_notes (question_id)",
        # Lecture materials / chunks
        "CREATE INDEX IF NOT EXISTS idx_lecture_materials_lecture_id_uploaded ON lecture_materials (lecture_id, uploaded_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_lecture_chunks_material_id ON lecture_chunks (material_id)",
        "CREATE INDEX IF NOT EXISTS idx_lecture_chunks_lecture_id ON lecture_chunks (lecture_id)",
        # Question chunk matches (evidence)
        "CREATE INDEX IF NOT EXISTS idx_question_chunk_matches_question ON question_chunk_matches (question_id)",
        "CREATE INDEX IF NOT EXISTS idx_question_chunk_matches_lecture ON question_chunk_matches (lecture_id)",
        "CREATE INDEX IF NOT EXISTS idx_question_chunk_matches_chunk ON question_chunk_matches (chunk_id)",
        "CREATE INDEX IF NOT EXISTS idx_question_chunk_matches_job ON question_chunk_matches (job_id)",
        # Practice answers / sessions
        "CREATE INDEX IF NOT EXISTS idx_practice_answers_session_id ON practice_answers (session_id)",
        "CREATE INDEX IF NOT EXISTS idx_practice_answers_question_id ON practice_answers (question_id)",
        "CREATE INDEX IF NOT EXISTS idx_practice_answers_answered_at ON practice_answers (answered_at)",
        "CREATE INDEX IF NOT EXISTS idx_practice_sessions_user_created ON practice_sessions (user_id, created_at DESC)",
        # Classification jobs
        "CREATE INDEX IF NOT EXISTS idx_classification_jobs_created_at ON classification_jobs (created_at DESC)",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply Postgres performance indexes.")
    parser.add_argument("--db", required=True, help="Postgres DB URI.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--analyze", action="store_true", help="Run ANALYZE afterwards.")
    args = parser.parse_args()

    db_uri = _normalize_db_uri(args.db)
    statements = _index_statements()

    if args.dry_run:
        for stmt in statements:
            print(stmt + ";")
        if args.analyze:
            print("ANALYZE;")
        return

    engine = create_engine(db_uri)
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
        if args.analyze:
            conn.execute(text("ANALYZE"))

    print(f"Applied {len(statements)} indexes.")


if __name__ == "__main__":
    main()
