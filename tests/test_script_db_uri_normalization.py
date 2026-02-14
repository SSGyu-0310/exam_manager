from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_module(module_name: str, filename: str):
    root = Path(__file__).resolve().parents[1]
    module_path = root / "scripts" / filename
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("module_name", "filename"),
    [
        ("init_db", "init_db.py"),
        ("migrate_ai_fields", "migrate_ai_fields.py"),
        ("build_queries", "build_queries.py"),
        ("dump_retrieval_features", "dump_retrieval_features.py"),
        ("tune_autoconfirm_v2", "tune_autoconfirm_v2.py"),
        ("evaluate_evalset", "evaluate_evalset.py"),
    ],
)
def test_normalize_db_uri_accepts_postgres_variants(module_name: str, filename: str):
    mod = _load_module(module_name, filename)

    assert mod._normalize_db_uri(None) is None
    assert (
        mod._normalize_db_uri("postgres://u:p@localhost:5432/exam_test")
        == "postgresql+psycopg://u:p@localhost:5432/exam_test"
    )
    assert (
        mod._normalize_db_uri("postgresql://u:p@localhost:5432/exam_test")
        == "postgresql+psycopg://u:p@localhost:5432/exam_test"
    )
    assert (
        mod._normalize_db_uri("postgresql+psycopg://u:p@localhost:5432/exam_test")
        == "postgresql+psycopg://u:p@localhost:5432/exam_test"
    )


@pytest.mark.parametrize(
    ("module_name", "filename"),
    [
        ("init_db_invalid", "init_db.py"),
        ("migrate_ai_fields_invalid", "migrate_ai_fields.py"),
        ("build_queries_invalid", "build_queries.py"),
        ("dump_retrieval_features_invalid", "dump_retrieval_features.py"),
        ("tune_autoconfirm_v2_invalid", "tune_autoconfirm_v2.py"),
        ("evaluate_evalset_invalid", "evaluate_evalset.py"),
    ],
)
def test_normalize_db_uri_rejects_sqlite_or_path(module_name: str, filename: str):
    mod = _load_module(module_name, filename)

    expected = "PostgreSQL URI"
    with pytest.raises(RuntimeError, match=expected):
        mod._normalize_db_uri("sqlite:///tmp/exam.db")

    with pytest.raises(RuntimeError, match=expected):
        mod._normalize_db_uri("/tmp/exam.db")


def test_init_fts_normalize_db_uri_accepts_postgres_variants():
    mod = _load_module("init_fts", "init_fts.py")

    assert (
        mod._normalize_db_uri("postgres://u:p@localhost:5432/exam_test")
        == "postgresql+psycopg://u:p@localhost:5432/exam_test"
    )
    assert (
        mod._normalize_db_uri("postgresql://u:p@localhost:5432/exam_test")
        == "postgresql+psycopg://u:p@localhost:5432/exam_test"
    )
    assert (
        mod._normalize_db_uri("postgresql+psycopg://u:p@localhost:5432/exam_test")
        == "postgresql+psycopg://u:p@localhost:5432/exam_test"
    )


def test_init_fts_normalize_db_uri_rejects_sqlite():
    mod = _load_module("init_fts_invalid", "init_fts.py")
    with pytest.raises(RuntimeError, match="supports PostgreSQL URI only"):
        mod._normalize_db_uri("sqlite:///tmp/exam.db")
