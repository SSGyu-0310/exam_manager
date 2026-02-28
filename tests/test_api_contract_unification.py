from __future__ import annotations

import json
import os

import pytest
from flask_jwt_extended import create_access_token

from app import create_app, db
from app.models import Block, ClassificationJob, Lecture, PreviousExam, Question, User


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


def test_ai_super_classify_start_blocks_unscoped_exam_access(
    client, app, monkeypatch
):
    with app.app_context():
        owner = _create_user("contract-super-owner@example.com")
        attacker = _create_user("contract-super-attacker@example.com")
        exam = PreviousExam(title="Owner Exam", user_id=owner.id)
        db.session.add(exam)
        db.session.flush()
        question = Question(
            exam_id=exam.id,
            user_id=owner.id,
            question_number=1,
            content="owner-only question",
            q_type=Question.TYPE_MULTIPLE_CHOICE,
            answer="1",
            is_classified=False,
            lecture_id=None,
        )
        db.session.add(question)
        db.session.commit()
        exam_id = exam.id
        token = _token_for(attacker)

    monkeypatch.setattr("app.routes.ai.GENAI_AVAILABLE", True)
    response = client.post(
        "/ai/classify/super/start",
        headers=_auth_header(token),
        json={"exam_id": exam_id},
    )

    assert response.status_code == 404
    payload = response.get_json()
    _assert_contract_shape(payload)
    assert payload["ok"] is False
    assert payload["code"] == "EXAM_NOT_FOUND"


def test_ai_super_classify_start_requires_block_id(client, app, monkeypatch):
    with app.app_context():
        user = _create_user("contract-super-block-required@example.com")
        token = _token_for(user)
        block = Block(name="Subject Block", subject="생리학", user_id=user.id)
        db.session.add(block)
        db.session.flush()
        lecture = Lecture(block_id=block.id, title="Scope Lecture", user_id=user.id)
        exam = PreviousExam(title="Scope Exam", subject="생리학", user_id=user.id)
        db.session.add_all([lecture, exam])
        db.session.flush()
        question = Question(
            exam_id=exam.id,
            user_id=user.id,
            question_number=1,
            content="scope question",
            q_type=Question.TYPE_MULTIPLE_CHOICE,
            answer="1",
            is_classified=False,
            lecture_id=None,
        )
        db.session.add(question)
        db.session.commit()
        exam_id = exam.id

    monkeypatch.setattr("app.routes.ai.GENAI_AVAILABLE", True)
    response = client.post(
        "/ai/classify/super/start",
        headers=_auth_header(token),
        json={"exam_id": exam_id},
    )

    assert response.status_code == 400
    payload = response.get_json()
    _assert_contract_shape(payload)
    assert payload["ok"] is False
    assert payload["code"] == "SUPER_BLOCK_ID_REQUIRED"


def test_ai_super_classify_start_rejects_subject_mismatch(client, app, monkeypatch):
    with app.app_context():
        user = _create_user("contract-super-subject-mismatch@example.com")
        token = _token_for(user)
        block = Block(name="Mismatch Block", subject="해부학", user_id=user.id)
        db.session.add(block)
        db.session.flush()
        lecture = Lecture(block_id=block.id, title="Mismatch Lecture", user_id=user.id)
        exam = PreviousExam(title="Mismatch Exam", subject="생리학", user_id=user.id)
        db.session.add_all([lecture, exam])
        db.session.flush()
        question = Question(
            exam_id=exam.id,
            user_id=user.id,
            question_number=1,
            content="mismatch question",
            q_type=Question.TYPE_MULTIPLE_CHOICE,
            answer="1",
            is_classified=False,
            lecture_id=None,
        )
        db.session.add(question)
        db.session.commit()
        exam_id = exam.id
        block_id = block.id

    monkeypatch.setattr("app.routes.ai.GENAI_AVAILABLE", True)
    response = client.post(
        "/ai/classify/super/start",
        headers=_auth_header(token),
        json={"exam_id": exam_id, "block_id": block_id},
    )

    assert response.status_code == 400
    payload = response.get_json()
    _assert_contract_shape(payload)
    assert payload["ok"] is False
    assert payload["code"] == "SUPER_SCOPE_SUBJECT_MISMATCH"
    assert payload["data"]["block_id"] == block_id


def test_ai_super_classify_start_reuses_recent_job(client, app, monkeypatch):
    with app.app_context():
        user = _create_user("contract-super-reuse@example.com")
        token = _token_for(user)
        block = Block(name="Reuse Block", subject="생리학", user_id=user.id)
        db.session.add(block)
        db.session.flush()
        lecture = Lecture(block_id=block.id, title="Reuse Lecture", user_id=user.id)
        exam = PreviousExam(title="Reuse Exam", subject="생리학", user_id=user.id)
        db.session.add_all([lecture, exam])
        db.session.flush()
        question = Question(
            exam_id=exam.id,
            user_id=user.id,
            question_number=1,
            content="reuse question",
            q_type=Question.TYPE_MULTIPLE_CHOICE,
            answer="1",
            is_classified=False,
            lecture_id=None,
        )
        db.session.add(question)
        db.session.commit()
        exam_id = exam.id

        existing_job = ClassificationJob(
            status=ClassificationJob.STATUS_PENDING,
            total_count=1,
            result_json=json.dumps(
                {
                    "request": {
                        "question_ids": [question.id],
                        "signature": "super-signature",
                    },
                    "results": [],
                },
                ensure_ascii=False,
            ),
        )
        db.session.add(existing_job)
        db.session.commit()
        existing_job_id = existing_job.id
        block_id = block.id

    monkeypatch.setattr("app.routes.ai.GENAI_AVAILABLE", True)
    monkeypatch.setattr(
        "app.routes.ai._build_super_request_signature",
        lambda exam_id, question_ids, idempotency_key=None, scope=None: "super-signature",
    )

    def _fail_start(
        cls,
        exam_id,
        request_meta=None,
        lecture_ids=None,
        question_ids=None,
        **kwargs,
    ):
        raise AssertionError(
            "new super job must not be enqueued when reusable job exists"
        )

    monkeypatch.setattr(
        "app.services.super_classifier.SuperClassifier.start_super_classification_job",
        classmethod(_fail_start),
    )

    response = client.post(
        "/ai/classify/super/start",
        headers=_auth_header(token),
        json={"exam_id": exam_id, "block_id": block_id},
    )

    assert response.status_code == 200
    payload = response.get_json()
    _assert_contract_shape(payload)
    assert payload["ok"] is True
    assert payload["data"]["job_id"] == existing_job_id
    assert payload["data"]["reused"] is True
    assert payload["data"]["super_classify"] is True


def test_ai_super_classify_start_passes_scoped_lectures_and_signature(
    client, app, monkeypatch
):
    with app.app_context():
        user = _create_user("contract-super-success@example.com")
        token = _token_for(user)
        block = Block(name="Super Block", subject="생리학", user_id=user.id)
        db.session.add(block)
        db.session.flush()
        lecture = Lecture(block_id=block.id, title="Scoped Lecture", user_id=user.id)
        exam = PreviousExam(title="Super Exam", subject="생리학", user_id=user.id)
        db.session.add_all([lecture, exam])
        db.session.flush()
        question = Question(
            exam_id=exam.id,
            user_id=user.id,
            question_number=1,
            content="super question",
            q_type=Question.TYPE_MULTIPLE_CHOICE,
            answer="1",
            is_classified=False,
            lecture_id=None,
        )
        db.session.add(question)
        db.session.commit()
        exam_id = exam.id
        question_id = question.id
        lecture_id = lecture.id
        block_id = block.id

    captured: dict[str, object] = {}

    def _fake_start(
        cls,
        exam_id,
        request_meta=None,
        lecture_ids=None,
        question_ids=None,
        **kwargs,
    ):
        captured["exam_id"] = exam_id
        captured["request_meta"] = request_meta or {}
        captured["lecture_ids"] = lecture_ids or []
        captured["question_ids"] = question_ids or []
        return 9876

    monkeypatch.setattr("app.routes.ai.GENAI_AVAILABLE", True)
    monkeypatch.setattr(
        "app.services.super_classifier.SuperClassifier.start_super_classification_job",
        classmethod(_fake_start),
    )

    response = client.post(
        "/ai/classify/super/start",
        headers=_auth_header(token),
        json={
            "exam_id": exam_id,
            "block_id": block_id,
            "idempotency_key": "local-run-001",
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    _assert_contract_shape(payload)
    assert payload["ok"] is True
    assert payload["data"]["job_id"] == 9876
    assert payload["data"]["reused"] is False
    assert payload["data"]["super_classify"] is True
    assert payload["data"]["request_signature"]

    request_meta = captured["request_meta"]
    assert captured["exam_id"] == exam_id
    assert captured["question_ids"] == [question_id]
    assert captured["lecture_ids"] == [lecture_id]
    assert request_meta["super_classify"] is True
    assert request_meta["exam_id"] == exam_id
    assert request_meta["question_ids"] == [question_id]
    assert request_meta["scope"]["block_id"] == block_id
    assert request_meta["scope"]["include_descendants"] is True
    assert request_meta["scope"]["lecture_ids"] == [lecture_id]
    assert request_meta["idempotency_key"] == "local-run-001"
    assert request_meta["signature"] == payload["data"]["request_signature"]


def test_ai_super_classify_start_allows_trusted_local_email_override(
    client, app, monkeypatch
):
    with app.app_context():
        owner = _create_user("contract-super-owner-2@example.com")
        trusted_user = _create_user("hisukgyu@gmail.com")
        token = _token_for(trusted_user)
        block = Block(name="Owner Block", subject="약리학", user_id=owner.id)
        db.session.add(block)
        db.session.flush()
        lecture = Lecture(block_id=block.id, title="Owner Lecture", user_id=owner.id)
        exam = PreviousExam(title="Owner Exam 2", subject="약리학", user_id=owner.id)
        db.session.add_all([lecture, exam])
        db.session.flush()
        question = Question(
            exam_id=exam.id,
            user_id=owner.id,
            question_number=1,
            content="owner question",
            q_type=Question.TYPE_MULTIPLE_CHOICE,
            answer="1",
            is_classified=False,
            lecture_id=None,
        )
        db.session.add(question)
        db.session.commit()
        exam_id = exam.id
        question_id = question.id
        lecture_id = lecture.id
        block_id = block.id

    captured: dict[str, object] = {}

    def _fake_start(
        cls,
        exam_id,
        request_meta=None,
        lecture_ids=None,
        question_ids=None,
        **kwargs,
    ):
        captured["exam_id"] = exam_id
        captured["lecture_ids"] = lecture_ids or []
        captured["question_ids"] = question_ids or []
        return 2468

    monkeypatch.setattr("app.routes.ai.GENAI_AVAILABLE", True)
    monkeypatch.setattr(
        "app.services.super_classifier.SuperClassifier.start_super_classification_job",
        classmethod(_fake_start),
    )

    response = client.post(
        "/ai/classify/super/start",
        headers=_auth_header(token),
        json={"exam_id": exam_id, "block_id": block_id},
    )

    assert response.status_code == 200
    payload = response.get_json()
    _assert_contract_shape(payload)
    assert payload["ok"] is True
    assert payload["data"]["job_id"] == 2468
    assert captured["exam_id"] == exam_id
    assert captured["question_ids"] == [question_id]
    assert lecture_id in captured["lecture_ids"]


def test_ai_super_classify_apply_allows_trusted_local_email_override(
    client, app, monkeypatch
):
    with app.app_context():
        owner = _create_user("contract-super-owner-3@example.com")
        trusted_user = _create_user("hisukgyu@gmail.com")
        token = _token_for(trusted_user)
        block = Block(name="Owner Block 3", user_id=owner.id)
        db.session.add(block)
        db.session.flush()
        lecture = Lecture(
            block_id=block.id, title="Owner Lecture 3", user_id=owner.id
        )
        exam = PreviousExam(title="Owner Exam 3", user_id=owner.id)
        db.session.add_all([lecture, exam])
        db.session.flush()
        question = Question(
            exam_id=exam.id,
            user_id=owner.id,
            question_number=1,
            content="owner question 3",
            q_type=Question.TYPE_MULTIPLE_CHOICE,
            answer="1",
            is_classified=False,
            lecture_id=None,
        )
        db.session.add(question)
        db.session.flush()
        job = ClassificationJob(
            status=ClassificationJob.STATUS_COMPLETED,
            total_count=1,
            success_count=1,
            processed_count=1,
            result_json=json.dumps(
                {
                    "request": {
                        "super_classify": True,
                        "question_ids": [question.id],
                    },
                    "results": [
                        {
                            "question_id": question.id,
                            "lecture_id": lecture.id,
                            "confidence": 0.8,
                            "no_match": False,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
        )
        db.session.add(job)
        db.session.commit()
        question_id = question.id
        job_id = job.id

    captured: dict[str, object] = {}

    def _fake_apply(
        question_ids,
        job_id,
        apply_mode="all",
        *,
        return_report=False,
    ):
        captured["question_ids"] = list(question_ids)
        captured["job_id"] = job_id
        if return_report:
            return len(question_ids), {"applied_ids": list(question_ids)}
        return len(question_ids)

    monkeypatch.setattr("app.routes.ai.apply_classification_results", _fake_apply)
    monkeypatch.setattr(
        "app.routes.ai.build_job_diagnostics",
        lambda *args, **kwargs: {"summary": {}},
    )

    response = client.post(
        "/ai/classify/apply",
        headers=_auth_header(token),
        json={
            "job_id": job_id,
            "question_ids": [question_id],
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    _assert_contract_shape(payload)
    assert payload["ok"] is True
    assert captured["job_id"] == job_id
    assert captured["question_ids"] == [question_id]
