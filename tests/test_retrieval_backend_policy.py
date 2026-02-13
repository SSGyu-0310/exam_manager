from types import SimpleNamespace

import pytest

from app.services import retrieval


def _cfg(search_backend: str):
    return SimpleNamespace(experiment=SimpleNamespace(search_backend=search_backend))


def test_resolve_search_backend_requires_postgres_runtime(monkeypatch):
    monkeypatch.setattr(retrieval, "is_postgres", lambda: False)
    monkeypatch.setattr(retrieval, "get_config", lambda: _cfg("auto"))

    with pytest.raises(RuntimeError, match="requires PostgreSQL runtime"):
        retrieval._resolve_search_backend()


def test_resolve_search_backend_accepts_postgres_runtime(monkeypatch):
    monkeypatch.setattr(retrieval, "is_postgres", lambda: True)
    monkeypatch.setattr(retrieval, "get_config", lambda: _cfg("postgres"))

    assert retrieval._resolve_search_backend() == "postgres"
