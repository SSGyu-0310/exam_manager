import os
from urllib.parse import urlparse

import pytest

from app import create_app, db


def _resolve_test_db_uri() -> str:
    db_uri = (os.environ.get("TEST_DATABASE_URL") or "").strip()
    if not db_uri:
        raise RuntimeError(
            "TEST_DATABASE_URL is required for pytest "
            "(must point to a Postgres test database)."
        )

    if db_uri.startswith(("postgresql://", "postgresql+psycopg://", "postgres://")):
        parsed = urlparse(db_uri)
        db_name = (parsed.path or "").lstrip("/")
        if not db_name or "test" not in db_name.lower():
            raise RuntimeError(
                "Refusing to run pytest on non-test Postgres DB. "
                "Use TEST_DATABASE_URL with a database name containing 'test'."
            )
        return db_uri

    raise RuntimeError(
        "Unsupported TEST_DATABASE_URL scheme. "
        "Use postgresql+psycopg://..."
    )


@pytest.fixture()
def app():
    db_uri = _resolve_test_db_uri()
    prev_jwt_secret = os.environ.get("JWT_SECRET_KEY")
    os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-at-least-32-bytes-long"
    try:
        app = create_app(
            "default",
            db_uri_override=db_uri,
            skip_migration_check=True,
        )
    finally:
        if prev_jwt_secret is None:
            os.environ.pop("JWT_SECRET_KEY", None)
        else:
            os.environ["JWT_SECRET_KEY"] = prev_jwt_secret
    app.config["TESTING"] = True
    app.config["LOCAL_ADMIN_ONLY"] = False
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
