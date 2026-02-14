-- Promote business invariants to PostgreSQL constraints.
-- Usage example:
--   psql "$DATABASE_URL" -f migrations/postgres/20260213_1500_integrity_constraints.sql

BEGIN;

-- ---------------------------------------------------------------------------
-- questions
-- ---------------------------------------------------------------------------
ALTER TABLE questions
  ALTER COLUMN is_classified SET DEFAULT FALSE,
  ALTER COLUMN classification_status SET DEFAULT 'manual',
  ALTER COLUMN q_type SET DEFAULT 'multiple_choice',
  ALTER COLUMN created_at SET DEFAULT NOW(),
  ALTER COLUMN updated_at SET DEFAULT NOW();

UPDATE questions
SET is_classified = COALESCE(is_classified, FALSE),
    classification_status = COALESCE(NULLIF(classification_status, ''), 'manual'),
    q_type = COALESCE(NULLIF(q_type, ''), 'multiple_choice'),
    created_at = COALESCE(created_at, NOW()),
    updated_at = COALESCE(updated_at, NOW())
WHERE is_classified IS NULL
   OR classification_status IS NULL
   OR classification_status = ''
   OR q_type IS NULL
   OR q_type = ''
   OR created_at IS NULL
   OR updated_at IS NULL;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM questions
    GROUP BY exam_id, question_number
    HAVING COUNT(*) > 1
  ) THEN
    RAISE EXCEPTION
      'Cannot enforce unique (exam_id, question_number): duplicates exist in questions.';
  END IF;
END $$;

ALTER TABLE questions
  ALTER COLUMN question_number SET NOT NULL,
  ALTER COLUMN is_classified SET NOT NULL,
  ALTER COLUMN classification_status SET NOT NULL,
  ALTER COLUMN q_type SET NOT NULL,
  ALTER COLUMN created_at SET NOT NULL,
  ALTER COLUMN updated_at SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_questions_exam_question_number
ON questions (exam_id, question_number);

-- ---------------------------------------------------------------------------
-- question_chunk_matches
-- ---------------------------------------------------------------------------
ALTER TABLE question_chunk_matches
  ALTER COLUMN source SET DEFAULT 'ai',
  ALTER COLUMN is_primary SET DEFAULT FALSE,
  ALTER COLUMN created_at SET DEFAULT NOW();

UPDATE question_chunk_matches
SET source = COALESCE(NULLIF(source, ''), 'ai'),
    is_primary = COALESCE(is_primary, FALSE),
    created_at = COALESCE(created_at, NOW())
WHERE source IS NULL
   OR source = ''
   OR is_primary IS NULL
   OR created_at IS NULL;

WITH ranked AS (
  SELECT
    id,
    ROW_NUMBER() OVER (
      PARTITION BY question_id, chunk_id, source
      ORDER BY is_primary DESC, id ASC
    ) AS rn
  FROM question_chunk_matches
)
DELETE FROM question_chunk_matches qcm
USING ranked r
WHERE qcm.id = r.id
  AND r.rn > 1;

ALTER TABLE question_chunk_matches
  ALTER COLUMN source SET NOT NULL,
  ALTER COLUMN is_primary SET NOT NULL,
  ALTER COLUMN created_at SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_question_chunk_matches_question_chunk_source
ON question_chunk_matches (question_id, chunk_id, source);

-- ---------------------------------------------------------------------------
-- classification_jobs
-- ---------------------------------------------------------------------------
ALTER TABLE classification_jobs
  ALTER COLUMN status SET DEFAULT 'pending',
  ALTER COLUMN total_count SET DEFAULT 0,
  ALTER COLUMN processed_count SET DEFAULT 0,
  ALTER COLUMN success_count SET DEFAULT 0,
  ALTER COLUMN failed_count SET DEFAULT 0,
  ALTER COLUMN created_at SET DEFAULT NOW(),
  ALTER COLUMN updated_at SET DEFAULT NOW();

UPDATE classification_jobs
SET status = COALESCE(NULLIF(status, ''), 'pending'),
    total_count = COALESCE(total_count, 0),
    processed_count = COALESCE(processed_count, 0),
    success_count = COALESCE(success_count, 0),
    failed_count = COALESCE(failed_count, 0),
    created_at = COALESCE(created_at, NOW()),
    updated_at = COALESCE(updated_at, NOW())
WHERE status IS NULL
   OR status = ''
   OR total_count IS NULL
   OR processed_count IS NULL
   OR success_count IS NULL
   OR failed_count IS NULL
   OR created_at IS NULL
   OR updated_at IS NULL;

ALTER TABLE classification_jobs
  ALTER COLUMN status SET NOT NULL,
  ALTER COLUMN total_count SET NOT NULL,
  ALTER COLUMN processed_count SET NOT NULL,
  ALTER COLUMN success_count SET NOT NULL,
  ALTER COLUMN failed_count SET NOT NULL,
  ALTER COLUMN created_at SET NOT NULL,
  ALTER COLUMN updated_at SET NOT NULL;

COMMIT;
