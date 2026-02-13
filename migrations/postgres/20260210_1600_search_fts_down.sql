-- Rollback for Postgres search upgrade
-- Usage example:
--   psql "$DATABASE_URL" -f migrations/postgres/20260210_1600_search_fts_down.sql

BEGIN;

DROP INDEX IF EXISTS idx_lecture_chunks_content_trgm;
DROP INDEX IF EXISTS idx_lecture_chunks_content_tsv;

DROP TRIGGER IF EXISTS lecture_chunks_tsv_trigger ON lecture_chunks;
DROP FUNCTION IF EXISTS lecture_chunks_tsv_update();

ALTER TABLE lecture_chunks
DROP COLUMN IF EXISTS content_tsv;

COMMIT;
