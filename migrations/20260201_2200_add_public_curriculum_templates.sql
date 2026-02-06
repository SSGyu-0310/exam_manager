-- Migration: Add PublicCurriculumTemplate table
-- Created: 2026-02-01

CREATE TABLE IF NOT EXISTS public_curriculum_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(300) NOT NULL,
    school_tag VARCHAR(100),
    grade_tag VARCHAR(50),
    subject_tag VARCHAR(100),
    description TEXT,
    payload_json TEXT NOT NULL,
    published BOOLEAN DEFAULT 0,
    created_by INTEGER REFERENCES users(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for filtering
CREATE INDEX IF NOT EXISTS idx_pct_published ON public_curriculum_templates(published);
CREATE INDEX IF NOT EXISTS idx_pct_school_tag ON public_curriculum_templates(school_tag);
CREATE INDEX IF NOT EXISTS idx_pct_grade_tag ON public_curriculum_templates(grade_tag);
CREATE INDEX IF NOT EXISTS idx_pct_subject_tag ON public_curriculum_templates(subject_tag);
