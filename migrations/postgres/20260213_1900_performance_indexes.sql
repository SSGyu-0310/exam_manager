-- Performance indexes for search/classification/manage hot paths.
-- Usage example:
--   psql "$DATABASE_URL" -f migrations/postgres/20260213_1900_performance_indexes.sql

BEGIN;

-- ---------------------------------------------------------------------------
-- Manage screen counts + recent exam aggregation
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_previous_exams_user_created_at
ON previous_exams (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_questions_user_id
ON questions (user_id);

CREATE INDEX IF NOT EXISTS idx_questions_user_is_classified
ON questions (user_id, is_classified);

CREATE INDEX IF NOT EXISTS idx_questions_user_exam_id
ON questions (user_id, exam_id);

CREATE INDEX IF NOT EXISTS idx_questions_exam_id_is_classified
ON questions (exam_id, is_classified);

-- ---------------------------------------------------------------------------
-- Classification apply / evidence persistence
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_question_chunk_matches_question_id
ON question_chunk_matches (question_id);

CREATE INDEX IF NOT EXISTS idx_classification_jobs_created_at_desc
ON classification_jobs (created_at DESC);

-- ---------------------------------------------------------------------------
-- Retrieval candidate hydration / lecture scope joins
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_lecture_chunks_lecture_id
ON lecture_chunks (lecture_id);

CREATE INDEX IF NOT EXISTS idx_lectures_block_id
ON lectures (block_id);

-- ---------------------------------------------------------------------------
-- Subject-scope matching (normalized comparisons in ai_classifier)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_blocks_subject_norm
ON blocks ((lower(btrim(coalesce(subject, '')))));

CREATE INDEX IF NOT EXISTS idx_subjects_name_norm
ON subjects ((lower(btrim(coalesce(name, '')))));

COMMIT;
