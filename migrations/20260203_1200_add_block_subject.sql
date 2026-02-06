-- Migration: Add subject column to blocks
-- Created: 2026-02-03

ALTER TABLE blocks ADD COLUMN subject VARCHAR(100);

CREATE INDEX IF NOT EXISTS idx_blocks_subject ON blocks(subject);
