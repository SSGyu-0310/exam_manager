import pytest

from app import create_app, db


@pytest.fixture()
def app():
    app = create_app(
        "default",
        db_uri_override="sqlite:///:memory:",
        skip_migration_check=True,
    )
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

