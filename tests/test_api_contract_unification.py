from __future__ import annotations

import os

import pytest
from flask_jwt_extended import create_access_token

from app import create_app, db
from app.models import PreviousExam, Question, User


@pytest.fixture()
def app(tmp_path):
    db_uri = f"sqlite:///{tmp_path / 'api_contract_unification.db'}"
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


def _create_user(email: str, password: str = "pw1234") -> User:
    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def _token_for(user: User) -> str:
    return create_access_token(identity=str(user.id))


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _assert_contract_shape(payload: dict):
    assert "ok" in payload
    assert "code" in payload
    assert "message" in payload
    assert "data" in payload


def test_api_auth_register_returns_standard_contract(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "contract-register@example.com", "password": "pw1234"},
    )

    assert response.status_code == 201
    payload = response.get_json()
    _assert_contract_shape(payload)
    assert payload["ok"] is True
    assert payload["code"] == "USER_REGISTERED"
    assert payload["message"] == "User registered successfully"
    assert payload["data"]["email"] == "contract-register@example.com"


def test_api_auth_login_failure_returns_standard_contract(client, app):
    with app.app_context():
        _create_user("contract-login@example.com", "pw1234")

    response = client.post(
        "/api/auth/login",
        json={"email": "contract-login@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    payload = response.get_json()
    _assert_contract_shape(payload)
    assert payload["ok"] is False
    assert payload["code"] == "INVALID_CREDENTIALS"
    assert payload["message"] == "Bad username or password"
    assert payload["data"] is None


def test_api_manage_summary_returns_standard_contract(client, app):
    with app.app_context():
        user = _create_user("contract-manage-summary@example.com")
        token = _token_for(user)

    response = client.get("/api/manage/summary", headers=_auth_header(token))

    assert response.status_code == 200
    payload = response.get_json()
    _assert_contract_shape(payload)
    assert payload["ok"] is True
    assert payload["code"] == "OK"
    assert "counts" in payload["data"]


def test_api_manage_not_found_error_returns_standard_contract(client, app):
    with app.app_context():
        user = _create_user("contract-manage-error@example.com")
        token = _token_for(user)

    response = client.get("/api/manage/blocks/999999", headers=_auth_header(token))

    assert response.status_code == 404
    payload = response.get_json()
    _assert_contract_shape(payload)
    assert payload["ok"] is False
    assert payload["code"] == "BLOCK_NOT_FOUND"
    assert payload["message"] == "Block not found."


def test_ai_classify_start_error_returns_standard_contract(client, app, monkeypatch):
    with app.app_context():
        user = _create_user("contract-ai-error@example.com")
        token = _token_for(user)

    monkeypatch.setattr("app.routes.ai.GENAI_AVAILABLE", True)

    response = client.post(
        "/ai/classify/start",
        headers=_auth_header(token),
        json={},
    )

    assert response.status_code == 400
    payload = response.get_json()
    _assert_contract_shape(payload)
    assert payload["ok"] is False
    assert payload["code"] == "QUESTION_IDS_REQUIRED"
    assert payload["message"] == "선택된 문제가 없습니다."
    assert payload["data"] is None


def test_ai_classify_start_success_returns_standard_contract(client, app, monkeypatch):
    with app.app_context():
        user = _create_user("contract-ai-success@example.com")
        token = _token_for(user)
        exam = PreviousExam(title="Contract Exam", user_id=user.id)
        db.session.add(exam)
        db.session.flush()
        question = Question(
            exam_id=exam.id,
            user_id=user.id,
            question_number=1,
            content="Contract test question",
            q_type=Question.TYPE_MULTIPLE_CHOICE,
            answer="1",
            is_classified=False,
            lecture_id=None,
        )
        db.session.add(question)
        db.session.commit()
        question_id = question.id

    monkeypatch.setattr("app.routes.ai.GENAI_AVAILABLE", True)
    monkeypatch.setattr(
        "app.routes.ai.AsyncBatchProcessor.start_classification_job",
        classmethod(lambda cls, question_ids, request_meta=None: 4321),
    )

    response = client.post(
        "/ai/classify/start",
        headers=_auth_header(token),
        json={"question_ids": [question_id]},
    )

    assert response.status_code == 200
    payload = response.get_json()
    _assert_contract_shape(payload)
    assert payload["ok"] is True
    assert payload["code"] == "OK"
    assert payload["data"]["job_id"] == 4321
    assert payload["data"]["status"] == "pending"
