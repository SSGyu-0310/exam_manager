-- Add current_question_index to practice_sessions for auto-save/resume support
ALTER TABLE practice_sessions
    ADD COLUMN IF NOT EXISTS current_question_index INTEGER DEFAULT 0;
