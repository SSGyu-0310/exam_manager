from __future__ import annotations

from sqlalchemy.engine import make_url

from app import db
from config import get_config


def get_db_backend() -> str:
    """Return the active DB backend name (sqlite/postgresql/...)."""
    try:
        bind = db.session.get_bind()
        if bind is not None:
            return bind.dialect.name
    except Exception:
        pass

    uri = get_config().runtime.db_uri
    if not uri:
        return "unknown"
    try:
        return make_url(uri).get_backend_name()
    except Exception:
        if uri.startswith("sqlite"):
            return "sqlite"
        if uri.startswith("postgres"):
            return "postgresql"
        return "unknown"


def is_sqlite() -> bool:
    return get_db_backend() == "sqlite"


def is_postgres() -> bool:
    backend = get_db_backend()
    return backend in ("postgresql", "postgres")

