from app.services.db_guard import guard_write_request


def _guard_json_result(app, method="POST"):
    with app.test_request_context(
        "/api/manage/exams",
        method=method,
        headers={"Accept": "application/json"},
    ):
        result = guard_write_request()
    return result


def test_guard_blocks_when_db_read_only(app):
    app.config["DB_READ_ONLY"] = True

    result = _guard_json_result(app, method="POST")

    assert result is not None
    response, status = result
    assert status == 503
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["code"] == "DB_READ_ONLY"


def test_guard_blocks_when_backup_enforced_but_disabled(app):
    app.config["ENV_NAME"] = "production"
    app.config["DB_READ_ONLY"] = False
    app.config["AUTO_BACKUP_BEFORE_WRITE"] = False
    app.config["ENFORCE_BACKUP_BEFORE_WRITE"] = True

    result = _guard_json_result(app, method="POST")

    assert result is not None
    response, status = result
    assert status == 503
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["code"] == "BACKUP_REQUIRED"


def test_guard_blocks_when_backup_enforced_on_postgres(app):
    app.config["ENV_NAME"] = "production"
    app.config["DB_READ_ONLY"] = False
    app.config["AUTO_BACKUP_BEFORE_WRITE"] = True
    app.config["ENFORCE_BACKUP_BEFORE_WRITE"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "postgresql+psycopg://u:p@localhost:5432/exam_test"
    )

    result = _guard_json_result(app, method="POST")

    assert result is not None
    response, status = result
    assert status == 503
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["code"] == "BACKUP_UNSUPPORTED"


def test_guard_blocks_when_backup_enforced_even_with_sqlite(app):
    app.config["ENV_NAME"] = "production"
    app.config["DB_READ_ONLY"] = False
    app.config["AUTO_BACKUP_BEFORE_WRITE"] = True
    app.config["ENFORCE_BACKUP_BEFORE_WRITE"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    result = _guard_json_result(app, method="POST")

    assert result is not None
    response, status = result
    assert status == 503
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["code"] == "BACKUP_UNSUPPORTED"
