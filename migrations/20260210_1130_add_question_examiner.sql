-- Add examiner metadata column to questions
ALTER TABLE questions ADD COLUMN examiner VARCHAR(120);
