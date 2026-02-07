-- Migration: Add subjects table and link blocks to subjects
-- Created: 2026-02-03

CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    "order" INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_subjects_user_name ON subjects(user_id, name);
CREATE INDEX IF NOT EXISTS idx_subjects_user_id ON subjects(user_id);

ALTER TABLE blocks ADD COLUMN subject_id INTEGER REFERENCES subjects(id);
CREATE INDEX IF NOT EXISTS idx_blocks_subject_id ON blocks(subject_id);

-- Create subjects from existing block.subject values
INSERT INTO subjects (user_id, name, created_at, updated_at)
SELECT DISTINCT b.user_id, TRIM(b.subject), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM blocks b
WHERE b.subject IS NOT NULL AND TRIM(b.subject) != ''
  AND NOT EXISTS (
      SELECT 1 FROM subjects s
      WHERE s.name = TRIM(b.subject)
        AND s.user_id IS b.user_id
  );

-- Link blocks to subjects based on subject name
UPDATE blocks
SET subject_id = (
    SELECT s.id FROM subjects s
    WHERE s.name = TRIM(blocks.subject)
      AND s.user_id IS blocks.user_id
)
WHERE blocks.subject IS NOT NULL AND TRIM(blocks.subject) != '';

-- Ensure physiology blocks are mapped under "생리학"
INSERT OR IGNORE INTO subjects (user_id, name, created_at, updated_at)
SELECT DISTINCT b.user_id, '생리학', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM blocks b
WHERE b.subject_id IS NULL AND b.name LIKE '생리학%';

UPDATE blocks
SET subject = '생리학',
    subject_id = (
        SELECT s.id FROM subjects s
        WHERE s.name = '생리학'
          AND s.user_id IS blocks.user_id
    )
WHERE blocks.subject_id IS NULL AND blocks.name LIKE '생리학%';
