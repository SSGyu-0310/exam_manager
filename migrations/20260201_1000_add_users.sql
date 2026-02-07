-- Create Users Table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(200),
    is_admin BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Add user_id columns
-- SQLite ALTER TABLE ADD COLUMN does not support adding constraints like NOT NULL directly without default, so we add as nullable.
ALTER TABLE blocks ADD COLUMN user_id INTEGER REFERENCES users(id);
ALTER TABLE lectures ADD COLUMN user_id INTEGER REFERENCES users(id);
ALTER TABLE previous_exams ADD COLUMN user_id INTEGER REFERENCES users(id);
ALTER TABLE questions ADD COLUMN user_id INTEGER REFERENCES users(id);
ALTER TABLE practice_sessions ADD COLUMN user_id INTEGER REFERENCES users(id);

-- Backfill default user (Admin) for existing data
INSERT INTO users (email, password_hash, is_admin) VALUES ('admin@local.host', 'pbkdf2:sha256:600000$Mz...', 1);
-- Note: Password hash is a placeholder, actual password reset needed or handled in app.

UPDATE blocks SET user_id = 1 WHERE user_id IS NULL;
UPDATE lectures SET user_id = 1 WHERE user_id IS NULL;
UPDATE previous_exams SET user_id = 1 WHERE user_id IS NULL;
UPDATE questions SET user_id = 1 WHERE user_id IS NULL;
UPDATE practice_sessions SET user_id = 1 WHERE user_id IS NULL;
