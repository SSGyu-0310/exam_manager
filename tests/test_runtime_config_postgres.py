import pytest

from config.runtime import _resolve_postgres_uri, get_runtime_config


def test_resolve_postgres_uri_normalizes_legacy_schemes():
    assert (
        _resolve_postgres_uri("postgres://u:p@localhost:5432/exam_test", "default")
        == "postgresql+psycopg://u:p@localhost:5432/exam_test"
    )
    assert (
        _resolve_postgres_uri("postgresql://u:p@localhost:5432/exam_test", "default")
        == "postgresql+psycopg://u:p@localhost:5432/exam_test"
    )
    assert (
        _resolve_postgres_uri(
            "postgresql+psycopg://u:p@localhost:5432/exam_test", "default"
        )
        == "postgresql+psycopg://u:p@localhost:5432/exam_test"
    )


def test_resolve_postgres_uri_rejects_sqlite():
    with pytest.raises(RuntimeError, match="SQLite/DB_PATH fallback has been removed"):
        _resolve_postgres_uri("sqlite:///tmp/exam.db", "default")


def test_get_runtime_config_requires_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("LOCAL_ADMIN_DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        get_runtime_config("default")


def test_get_runtime_config_local_admin_prefers_local_admin_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/main_db")
    monkeypatch.setenv(
        "LOCAL_ADMIN_DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/admin_db"
    )

    cfg = get_runtime_config("local_admin")

    assert cfg.db_uri == "postgresql+psycopg://u:p@localhost:5432/admin_db"
    assert cfg.local_admin_only is True
