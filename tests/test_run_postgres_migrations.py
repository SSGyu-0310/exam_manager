from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    module_path = root / "scripts" / "run_postgres_migrations.py"
    spec = importlib.util.spec_from_file_location("run_postgres_migrations", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_normalize_db_uri_variants() -> None:
    mod = _load_module()
    assert (
        mod._normalize_db_uri("postgresql+psycopg://u:p@localhost:5432/db")
        == "postgresql://u:p@localhost:5432/db"
    )
    assert (
        mod._normalize_db_uri("postgres://u:p@localhost:5432/db")
        == "postgresql://u:p@localhost:5432/db"
    )
    assert (
        mod._normalize_db_uri("postgresql://u:p@localhost:5432/db")
        == "postgresql://u:p@localhost:5432/db"
    )


def test_list_migrations_excludes_down_files(tmp_path: Path) -> None:
    mod = _load_module()
    (tmp_path / "20260210_1600_search_fts.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "20260210_1600_search_fts_down.sql").write_text(
        "SELECT 2;", encoding="utf-8"
    )
    (tmp_path / "note.txt").write_text("noop", encoding="utf-8")

    paths = mod._list_migrations(tmp_path)
    assert [p.name for p in paths] == ["20260210_1600_search_fts.sql"]


def test_strip_outer_transaction_removes_wrappers() -> None:
    mod = _load_module()
    sql = """
-- header
BEGIN;
CREATE TABLE demo (id INTEGER);
COMMIT;
"""
    stripped = mod._strip_outer_transaction(sql)
    assert "BEGIN;" not in stripped
    assert "COMMIT;" not in stripped
    assert "CREATE TABLE demo (id INTEGER);" in stripped


def test_strip_outer_transaction_keeps_plain_sql() -> None:
    mod = _load_module()
    sql = "CREATE TABLE demo (id INTEGER);"
    assert mod._strip_outer_transaction(sql) == sql


def test_strip_outer_transaction_preserves_preamble_statements() -> None:
    mod = _load_module()
    sql = """
SET search_path TO public;
BEGIN;
CREATE TABLE demo (id INTEGER);
COMMIT;
"""
    stripped = mod._strip_outer_transaction(sql)
    assert "BEGIN;" not in stripped
    assert "COMMIT;" not in stripped
    assert "SET search_path TO public;" in stripped
    assert "CREATE TABLE demo (id INTEGER);" in stripped


def test_split_sql_statements_handles_dollar_quoted_function() -> None:
    mod = _load_module()
    sql = """
CREATE OR REPLACE FUNCTION f_demo()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.content_tsv := to_tsvector('simple', coalesce(NEW.content, ''));
  RETURN NEW;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_demo ON lecture_chunks USING GIN (content_tsv);
"""
    statements = mod._split_sql_statements(sql)
    assert len(statements) == 2
    assert "FUNCTION f_demo" in statements[0]
    assert "CREATE INDEX IF NOT EXISTS idx_demo" in statements[1]
