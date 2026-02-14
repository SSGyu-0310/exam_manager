-- Postgres search upgrade (FTS + optional trigram fallback)
-- Usage example:
--   psql "$DATABASE_URL" -f migrations/postgres/20260210_1600_search_fts.sql

BEGIN;

ALTER TABLE lecture_chunks
ADD COLUMN IF NOT EXISTS content_tsv tsvector;

CREATE OR REPLACE FUNCTION lecture_chunks_tsv_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.content_tsv := to_tsvector('simple', coalesce(NEW.content, ''));
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lecture_chunks_tsv_trigger ON lecture_chunks;

CREATE TRIGGER lecture_chunks_tsv_trigger
BEFORE INSERT OR UPDATE OF content
ON lecture_chunks
FOR EACH ROW
EXECUTE FUNCTION lecture_chunks_tsv_update();

UPDATE lecture_chunks
SET content_tsv = to_tsvector('simple', coalesce(content, ''))
WHERE content_tsv IS NULL;

CREATE INDEX IF NOT EXISTS idx_lecture_chunks_content_tsv
ON lecture_chunks USING GIN (content_tsv);

-- Optional: typo/surface-form fallback (pg_trgm)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_lecture_chunks_content_trgm
ON lecture_chunks USING GIN (content gin_trgm_ops);

COMMIT;
