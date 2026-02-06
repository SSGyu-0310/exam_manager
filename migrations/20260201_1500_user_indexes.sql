CREATE INDEX IF NOT EXISTS idx_blocks_user_id ON blocks (user_id);
CREATE INDEX IF NOT EXISTS idx_lectures_user_id ON lectures (user_id);
CREATE INDEX IF NOT EXISTS idx_previous_exams_user_id ON previous_exams (user_id);
CREATE INDEX IF NOT EXISTS idx_questions_user_id ON questions (user_id);
CREATE INDEX IF NOT EXISTS idx_practice_sessions_user_id ON practice_sessions (user_id);
