from __future__ import annotations

import json
from datetime import datetime
from io import BytesIO
from pathlib import Path

from flask_jwt_extended import create_access_token

from app import db
from app.models import (
    Block,
    Choice,
    ClassificationJob,
    Lecture,
    LectureChunk,
    LectureMaterial,
    PreviousExam,
    Question,
    User,
)


def _create_user(email: str, password: str = "pw", *, is_admin: bool = False) -> User:
    user = User(email=email, is_admin=is_admin)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_upload_pdf_creates_exam_questions_and_choices(client, app, monkeypatch):
    with app.app_context():
        user = _create_user("gate-upload-success@example.com")
        user_id = user.id
        token = create_access_token(identity=str(user_id))

    def fake_parse_pdf(pdf_path, upload_dir, exam_prefix, mode="legacy", max_option_number=16):
        return [
            {
                "question_number": 1,
                "content": "Question 1",
                "options": [
                    {"number": 1, "content": "A", "is_correct": True},
                    {"number": 2, "content": "B", "is_correct": False},
                ],
                "answer_options": [1],
                "answer_text": "1",
            },
            {
                "question_number": 2,
                "content": "Question 2",
                "options": [
                    {"number": 1, "content": "C", "is_correct": False},
                    {"number": 2, "content": "D", "is_correct": True},
                ],
                "answer_options": [2],
                "answer_text": "2",
            },
        ]

    monkeypatch.setattr("app.services.pdf_parser_factory.parse_pdf", fake_parse_pdf)
    monkeypatch.setattr(
        "app.services.pdf_cropper.crop_pdf_to_questions",
        lambda *args, **kwargs: {
            "meta": {"questions": [{"qnum": 1}, {"qnum": 2}]},
            "question_images": {"1": "img1.png", "2": "img2.png"},
            "meta_path": None,
        },
    )
    monkeypatch.setattr(
        "app.services.pdf_cropper.to_static_relative",
        lambda *args, **kwargs: None,
    )

    response = client.post(
        "/api/manage/upload-pdf",
        headers=_auth_header(token),
        data={
            "pdf_file": (BytesIO(b"%PDF-1.4 fake"), "sample.pdf"),
            "subject": "Biology",
            "year": "2025",
            "term": "1\ucc28",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["data"]["questionCount"] == 2
    assert payload["data"]["choiceCount"] == 4

    with app.app_context():
        exam_id = payload["data"]["examId"]
        exam = db.session.get(PreviousExam, exam_id)
        assert exam is not None
        assert exam.user_id == user_id
        questions = (
            Question.query.filter_by(exam_id=exam_id)
            .order_by(Question.question_number.asc())
            .all()
        )
        assert len(questions) == 2
        assert questions[0].image_path == f"exam_crops/exam_{exam_id}/img1.png"
        assert questions[1].image_path == f"exam_crops/exam_{exam_id}/img2.png"
        choice_count = (
            Choice.query.join(Question, Choice.question_id == Question.id)
            .filter(Question.exam_id == exam_id)
            .count()
        )
        assert choice_count == 4


def test_upload_pdf_returns_400_when_parser_extracts_no_questions(client, app, monkeypatch):
    with app.app_context():
        user = _create_user("gate-upload-empty@example.com")
        token = create_access_token(identity=str(user.id))

    monkeypatch.setattr(
        "app.services.pdf_parser_factory.parse_pdf",
        lambda *args, **kwargs: [],
    )

    response = client.post(
        "/api/manage/upload-pdf",
        headers=_auth_header(token),
        data={
            "pdf_file": (BytesIO(b"%PDF-1.4 fake"), "empty.pdf"),
            "subject": "Biology",
            "year": "2025",
            "term": "2\ucc28",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["code"] == "PDF_PARSE_EMPTY"


def test_upload_pdf_falls_back_to_parser_images_when_crop_unreliable(client, app, monkeypatch):
    with app.app_context():
        user = _create_user("gate-upload-crop-fallback@example.com")
        token = create_access_token(identity=str(user.id))

    def fake_parse_pdf(pdf_path, upload_dir, exam_prefix, mode="legacy", max_option_number=16):
        return [
            {
                "question_number": 1,
                "content": "Question 1",
                "image_path": "parser_q1.png",
                "options": [],
                "answer_options": [],
                "answer_text": "",
            },
            {
                "question_number": 2,
                "content": "Question 2",
                "image_path": "parser_q2.png",
                "options": [],
                "answer_options": [],
                "answer_text": "",
            },
        ]

    monkeypatch.setattr("app.services.pdf_parser_factory.parse_pdf", fake_parse_pdf)
    monkeypatch.setattr(
        "app.services.pdf_cropper.crop_pdf_to_questions",
        lambda *args, **kwargs: {
            # Deliberately unreliable: only one cropped question for two parsed questions.
            "meta": {"questions": [{"qnum": 1}]},
            "question_images": {"1": "img1.png"},
            "meta_path": None,
        },
    )
    monkeypatch.setattr(
        "app.services.pdf_cropper.to_static_relative",
        lambda *args, **kwargs: None,
    )

    response = client.post(
        "/api/manage/upload-pdf",
        headers=_auth_header(token),
        data={
            "pdf_file": (BytesIO(b"%PDF-1.4 fake"), "sample.pdf"),
            "subject": "Biology",
            "year": "2025",
            "term": "1\ucc28",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["data"]["cropReliable"] is False

    with app.app_context():
        exam_id = payload["data"]["examId"]
        questions = (
            Question.query.filter_by(exam_id=exam_id)
            .order_by(Question.question_number.asc())
            .all()
        )
        assert len(questions) == 2
        assert questions[0].image_path == "parser_q1.png"
        assert questions[1].image_path == "parser_q2.png"


def test_upload_pdf_rejects_duplicate_question_numbers(client, app, monkeypatch):
    with app.app_context():
        user = _create_user("gate-upload-duplicate-qnum@example.com")
        user_id = user.id
        token = create_access_token(identity=str(user_id))

    def fake_parse_pdf(
        pdf_path, upload_dir, exam_prefix, mode="legacy", max_option_number=16
    ):
        return [
            {
                "question_number": 1,
                "content": "Question 1-A",
                "options": [{"number": 1, "content": "A", "is_correct": True}],
                "answer_options": [1],
                "answer_text": "1",
            },
            {
                "question_number": 1,
                "content": "Question 1-B",
                "options": [{"number": 1, "content": "B", "is_correct": True}],
                "answer_options": [1],
                "answer_text": "1",
            },
        ]

    monkeypatch.setattr("app.services.pdf_parser_factory.parse_pdf", fake_parse_pdf)
    monkeypatch.setattr(
        "app.services.pdf_cropper.crop_pdf_to_questions",
        lambda *args, **kwargs: {"meta": {"questions": []}, "question_images": {}, "meta_path": None},
    )
    monkeypatch.setattr(
        "app.services.pdf_cropper.to_static_relative",
        lambda *args, **kwargs: None,
    )

    response = client.post(
        "/api/manage/upload-pdf",
        headers=_auth_header(token),
        data={
            "pdf_file": (BytesIO(b"%PDF-1.4 fake"), "sample.pdf"),
            "subject": "Biology",
            "year": "2025",
            "term": "1\ucc28",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["code"] == "PDF_PARSE_INVALID"
    assert "Duplicate question number" in payload["message"]

    with app.app_context():
        assert PreviousExam.query.filter_by(user_id=user_id).count() == 0


def test_upload_pdf_rejects_invalid_answer_option_reference(client, app, monkeypatch):
    with app.app_context():
        user = _create_user("gate-upload-invalid-answer-option@example.com")
        user_id = user.id
        token = create_access_token(identity=str(user_id))

    def fake_parse_pdf(
        pdf_path, upload_dir, exam_prefix, mode="legacy", max_option_number=16
    ):
        return [
            {
                "question_number": 1,
                "content": "Question 1",
                "options": [
                    {"number": 1, "content": "A", "is_correct": False},
                    {"number": 2, "content": "B", "is_correct": False},
                ],
                "answer_options": [3],
                "answer_text": "3",
            }
        ]

    monkeypatch.setattr("app.services.pdf_parser_factory.parse_pdf", fake_parse_pdf)
    monkeypatch.setattr(
        "app.services.pdf_cropper.crop_pdf_to_questions",
        lambda *args, **kwargs: {"meta": {"questions": []}, "question_images": {}, "meta_path": None},
    )
    monkeypatch.setattr(
        "app.services.pdf_cropper.to_static_relative",
        lambda *args, **kwargs: None,
    )

    response = client.post(
        "/api/manage/upload-pdf",
        headers=_auth_header(token),
        data={
            "pdf_file": (BytesIO(b"%PDF-1.4 fake"), "sample.pdf"),
            "subject": "Biology",
            "year": "2025",
            "term": "1\ucc28",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["code"] == "PDF_PARSE_INVALID"
    assert "does not exist" in payload["message"]

    with app.app_context():
        assert PreviousExam.query.filter_by(user_id=user_id).count() == 0


def test_ai_classify_start_to_apply_flow(client, app, monkeypatch):
    with app.app_context():
        user = _create_user("gate-ai-flow@example.com")
        token = create_access_token(identity=str(user.id))

        block = Block(name="Circulation", user_id=user.id)
        db.session.add(block)
        db.session.flush()

        lecture = Lecture(block_id=block.id, title="Heart Cycle", user_id=user.id, order=1)
        exam = PreviousExam(title="Physiology-2025-1", user_id=user.id)
        db.session.add_all([lecture, exam])
        db.session.flush()

        question = Question(
            exam_id=exam.id,
            user_id=user.id,
            question_number=1,
            content="Which phase follows atrial systole?",
            q_type=Question.TYPE_MULTIPLE_CHOICE,
            answer="2",
            is_classified=False,
            lecture_id=None,
        )
        db.session.add(question)
        db.session.flush()

        question_id = question.id
        lecture_id = lecture.id
        lecture_title = lecture.title
        block_name = block.name
        db.session.commit()

    monkeypatch.setattr("app.routes.ai.GENAI_AVAILABLE", True)

    def fake_start_job(cls, question_ids, request_meta=None):
        results = [
            {
                "question_id": qid,
                "lecture_id": lecture_id,
                "lecture_title": lecture_title,
                "block_name": block_name,
                "no_match": False,
            }
            for qid in question_ids
        ]
        job = ClassificationJob(
            status=ClassificationJob.STATUS_COMPLETED,
            total_count=len(question_ids),
            processed_count=len(question_ids),
            success_count=len(question_ids),
            failed_count=0,
            completed_at=datetime.utcnow(),
            result_json=json.dumps({"request": request_meta or {}, "results": results}),
        )
        db.session.add(job)
        db.session.commit()
        return job.id

    monkeypatch.setattr(
        "app.routes.ai.AsyncBatchProcessor.start_classification_job",
        classmethod(fake_start_job),
    )
    monkeypatch.setattr(
        "app.routes.ai.apply_classification_results",
        lambda question_ids, job_id, apply_mode="all", return_report=False: (
            (len(question_ids), {"mode": apply_mode}) if return_report else len(question_ids)
        ),
    )

    start_response = client.post(
        "/ai/classify/start",
        headers=_auth_header(token),
        json={"question_ids": [question_id]},
    )
    assert start_response.status_code == 200
    start_payload = start_response.get_json()
    assert start_payload["success"] is True
    assert start_payload["ok"] is True
    job_id = start_payload["job_id"]

    status_response = client.get(
        f"/ai/classify/status/{job_id}", headers=_auth_header(token)
    )
    assert status_response.status_code == 200
    status_payload = status_response.get_json()
    assert status_payload["success"] is True
    assert status_payload["ok"] is True
    assert status_payload["status"] == ClassificationJob.STATUS_COMPLETED
    assert status_payload["is_complete"] is True

    result_response = client.get(
        f"/ai/classify/result/{job_id}", headers=_auth_header(token)
    )
    assert result_response.status_code == 200
    result_payload = result_response.get_json()
    assert result_payload["success"] is True
    assert result_payload["ok"] is True
    assert result_payload["summary"]["total"] == 1
    assert len(result_payload["grouped_results"]) == 1

    apply_response = client.post(
        "/ai/classify/apply",
        headers=_auth_header(token),
        json={"job_id": job_id, "question_ids": [question_id]},
    )
    assert apply_response.status_code == 200
    apply_payload = apply_response.get_json()
    assert apply_payload["success"] is True
    assert apply_payload["ok"] is True
    assert apply_payload["applied_count"] == 1


def test_ai_classify_start_preserves_explicit_empty_lecture_ids(client, app, monkeypatch):
    with app.app_context():
        user = _create_user("gate-ai-scope-empty-lectures@example.com")
        user_id = user.id
        token = create_access_token(identity=str(user_id))

        block = Block(name="Scope Control", user_id=user_id)
        db.session.add(block)
        db.session.flush()

        lecture = Lecture(
            block_id=block.id,
            title="Scope Control Lecture",
            user_id=user_id,
            order=1,
        )
        exam = PreviousExam(title="Scope-2026-1", user_id=user_id)
        db.session.add_all([lecture, exam])
        db.session.flush()

        question = Question(
            exam_id=exam.id,
            user_id=user_id,
            question_number=1,
            content="Scope preservation check?",
            q_type=Question.TYPE_MULTIPLE_CHOICE,
            answer="1",
            is_classified=False,
            lecture_id=None,
        )
        db.session.add(question)
        db.session.flush()
        question_id = question.id
        block_id = block.id
        db.session.commit()

    monkeypatch.setattr("app.routes.ai.GENAI_AVAILABLE", True)
    calls = []

    def fake_start_job(cls, question_ids, request_meta=None):
        calls.append({"question_ids": list(question_ids), "request_meta": request_meta or {}})
        job = ClassificationJob(
            status=ClassificationJob.STATUS_PENDING,
            total_count=len(question_ids),
            processed_count=0,
            success_count=0,
            failed_count=0,
            result_json=json.dumps({"request": request_meta or {}, "results": []}),
        )
        db.session.add(job)
        db.session.commit()
        return job.id

    monkeypatch.setattr(
        "app.routes.ai.AsyncBatchProcessor.start_classification_job",
        classmethod(fake_start_job),
    )

    response = client.post(
        "/ai/classify/start",
        headers=_auth_header(token),
        json={
            "question_ids": [question_id],
            "scope": {
                "block_id": block_id,
                "include_descendants": False,
                "lecture_ids": [],
            },
        },
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["ok"] is True
    assert len(calls) == 1

    request_meta = calls[0]["request_meta"]
    assert request_meta["scope_user_id"] == user_id
    assert request_meta["scope"] == {
        "block_id": block_id,
        "include_descendants": False,
        "lecture_ids": [],
    }


def test_ai_worker_fallback_resolve_uses_scope_user_context(app, monkeypatch):
    with app.app_context():
        user = _create_user("gate-ai-worker-scope-user@example.com")
        user_id = user.id

        block = Block(name="Legacy Scope Block", user_id=user_id)
        db.session.add(block)
        db.session.flush()

        exam = PreviousExam(title="Legacy-2026-1", user_id=user_id)
        db.session.add(exam)
        db.session.flush()

        question = Question(
            exam_id=exam.id,
            user_id=user_id,
            question_number=1,
            content="Legacy scope fallback question",
            q_type=Question.TYPE_MULTIPLE_CHOICE,
            answer="1",
            is_classified=False,
            lecture_id=None,
        )
        db.session.add(question)
        db.session.flush()

        question_id = question.id
        block_id = block.id
        request_meta = {
            "signature": "legacy-scope-fallback",
            "question_ids": [question_id],
            "scope_user_id": user_id,
            "scope": {
                "block_id": block_id,
                "include_descendants": False,
            },
        }
        job = ClassificationJob(
            status=ClassificationJob.STATUS_PENDING,
            total_count=1,
            processed_count=0,
            success_count=0,
            failed_count=0,
            result_json=json.dumps({"request": request_meta, "results": []}),
        )
        db.session.add(job)
        db.session.commit()
        job_id = job.id

    monkeypatch.setattr("app.create_app", lambda *_args, **_kwargs: app)
    app.config["PARENT_ENABLED"] = False

    resolve_calls = []

    def fake_resolve_lecture_ids(
        resolved_block_id,
        resolved_folder_id,
        include_descendants,
        user=None,
        include_public=False,
    ):
        resolve_calls.append(
            {
                "block_id": resolved_block_id,
                "folder_id": resolved_folder_id,
                "include_descendants": include_descendants,
                "user_id": getattr(user, "id", None),
                "include_public": include_public,
            }
        )
        return []

    class FakeRetriever:
        def refresh_cache(self):
            return None

        def find_candidates(self, _question_text, **_kwargs):
            return []

    class FakeClassifier:
        def classify_single(self, _question, _candidates):
            return {
                "lecture_id": None,
                "confidence": 0.0,
                "reason": "",
                "study_hint": "",
                "evidence": [],
                "no_match": True,
                "decision_mode": "no_match",
                "rejudge_attempted": False,
                "rejudge_decision_mode": None,
                "rejudge_confidence": None,
                "rejudge_reason": None,
                "final_decision_source": "pass1",
            }

    monkeypatch.setattr("app.services.ai_classifier.resolve_lecture_ids", fake_resolve_lecture_ids)
    monkeypatch.setattr("app.services.ai_classifier.LectureRetriever", FakeRetriever)
    monkeypatch.setattr("app.services.ai_classifier.GeminiClassifier", FakeClassifier)

    from app.services.ai_classifier import AsyncBatchProcessor

    AsyncBatchProcessor._process_job(job_id, [question_id])

    assert len(resolve_calls) == 1
    assert resolve_calls[0] == {
        "block_id": block_id,
        "folder_id": None,
        "include_descendants": False,
        "user_id": user_id,
        "include_public": True,
    }


def test_ai_classify_start_creates_new_job_when_previous_failed(client, app, monkeypatch):
    with app.app_context():
        user = _create_user("gate-ai-retry-default@example.com")
        token = create_access_token(identity=str(user.id))

        block = Block(name="Respiration", user_id=user.id)
        db.session.add(block)
        db.session.flush()

        exam = PreviousExam(title="Physiology-2025-2", user_id=user.id)
        db.session.add(exam)
        db.session.flush()

        question = Question(
            exam_id=exam.id,
            user_id=user.id,
            question_number=1,
            content="Gas exchange occurs in?",
            q_type=Question.TYPE_MULTIPLE_CHOICE,
            answer="1",
            is_classified=False,
            lecture_id=None,
        )
        db.session.add(question)
        db.session.flush()

        question_id = question.id

        from app.routes.ai import _build_request_signature

        signature = _build_request_signature([question_id], None, None)
        failed_job = ClassificationJob(
            status=ClassificationJob.STATUS_FAILED,
            total_count=1,
            processed_count=1,
            success_count=0,
            failed_count=1,
            error_message="GEMINI_API_KEY missing",
            completed_at=datetime.utcnow(),
            result_json=json.dumps(
                {
                    "request": {
                        "signature": signature,
                        "question_ids": [question_id],
                    },
                    "results": [],
                }
            ),
        )
        db.session.add(failed_job)
        db.session.commit()
        failed_job_id = failed_job.id

    monkeypatch.setattr("app.routes.ai.GENAI_AVAILABLE", True)
    calls = []

    def fake_start_job(cls, question_ids, request_meta=None):
        calls.append({"question_ids": list(question_ids), "request_meta": request_meta or {}})
        job = ClassificationJob(
            status=ClassificationJob.STATUS_PENDING,
            total_count=len(question_ids),
            processed_count=0,
            success_count=0,
            failed_count=0,
            result_json=json.dumps({"request": request_meta or {}, "results": []}),
        )
        db.session.add(job)
        db.session.commit()
        return job.id

    monkeypatch.setattr(
        "app.routes.ai.AsyncBatchProcessor.start_classification_job",
        classmethod(fake_start_job),
    )

    response = client.post(
        "/ai/classify/start",
        headers=_auth_header(token),
        json={"question_ids": [question_id]},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["ok"] is True
    assert payload["reused"] is False
    assert payload["job_id"] != failed_job_id
    assert len(calls) == 1


def test_ai_classify_start_returns_standard_error_shape(client, app, monkeypatch):
    with app.app_context():
        user = _create_user("gate-ai-error-shape@example.com")
        token = create_access_token(identity=str(user.id))

    monkeypatch.setattr("app.routes.ai.GENAI_AVAILABLE", True)

    response = client.post(
        "/ai/classify/start",
        headers=_auth_header(token),
        json={},
    )
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["success"] is False
    assert payload["code"] == "QUESTION_IDS_REQUIRED"
    assert payload["message"] == "선택된 문제가 없습니다."
    assert payload["error"] == payload["message"]


def test_ai_classify_start_reuses_non_failed_job(client, app, monkeypatch):
    with app.app_context():
        user = _create_user("gate-ai-reuse-existing@example.com")
        token = create_access_token(identity=str(user.id))

        block = Block(name="Neuro", user_id=user.id)
        db.session.add(block)
        db.session.flush()

        exam = PreviousExam(title="Anatomy-2025-1", user_id=user.id)
        db.session.add(exam)
        db.session.flush()

        question = Question(
            exam_id=exam.id,
            user_id=user.id,
            question_number=1,
            content="Neuron resting potential?",
            q_type=Question.TYPE_MULTIPLE_CHOICE,
            answer="3",
            is_classified=False,
            lecture_id=None,
        )
        db.session.add(question)
        db.session.flush()

        question_id = question.id

        from app.routes.ai import _build_request_signature

        signature = _build_request_signature([question_id], None, None)
        pending_job = ClassificationJob(
            status=ClassificationJob.STATUS_PENDING,
            total_count=1,
            processed_count=0,
            success_count=0,
            failed_count=0,
            result_json=json.dumps(
                {
                    "request": {
                        "signature": signature,
                        "question_ids": [question_id],
                    },
                    "results": [],
                }
            ),
        )
        db.session.add(pending_job)
        db.session.commit()
        pending_job_id = pending_job.id

    monkeypatch.setattr("app.routes.ai.GENAI_AVAILABLE", True)

    def fail_if_called(cls, question_ids, request_meta=None):
        raise AssertionError("start_classification_job should not be called when reusing")

    monkeypatch.setattr(
        "app.routes.ai.AsyncBatchProcessor.start_classification_job",
        classmethod(fail_if_called),
    )

    response = client.post(
        "/ai/classify/start",
        headers=_auth_header(token),
        json={"question_ids": [question_id]},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["ok"] is True
    assert payload["reused"] is True
    assert payload["job_id"] == pending_job_id


def test_ai_classify_cancel_marks_job_cancelled(client, app):
    with app.app_context():
        user = _create_user("gate-ai-cancel@example.com")
        token = create_access_token(identity=str(user.id))

        block = Block(name="Renal", user_id=user.id)
        db.session.add(block)
        db.session.flush()

        exam = PreviousExam(title="Physiology-2026-1", user_id=user.id)
        db.session.add(exam)
        db.session.flush()

        question = Question(
            exam_id=exam.id,
            user_id=user.id,
            question_number=1,
            content="Renal plasma flow marker?",
            q_type=Question.TYPE_MULTIPLE_CHOICE,
            answer="1",
            is_classified=False,
            lecture_id=None,
        )
        db.session.add(question)
        db.session.flush()

        from app.routes.ai import _build_request_signature

        signature = _build_request_signature([question.id], None, None)
        job = ClassificationJob(
            status=ClassificationJob.STATUS_PROCESSING,
            total_count=1,
            processed_count=0,
            success_count=0,
            failed_count=0,
            result_json=json.dumps(
                {
                    "request": {
                        "signature": signature,
                        "question_ids": [question.id],
                    },
                    "results": [],
                }
            ),
        )
        db.session.add(job)
        db.session.commit()
        job_id = job.id

    cancel_response = client.post(
        f"/ai/classify/cancel/{job_id}",
        headers=_auth_header(token),
    )
    assert cancel_response.status_code == 200
    cancel_payload = cancel_response.get_json()
    assert cancel_payload["success"] is True
    assert cancel_payload["ok"] is True
    assert cancel_payload["status"] == ClassificationJob.STATUS_CANCELLED

    status_response = client.get(
        f"/ai/classify/status/{job_id}",
        headers=_auth_header(token),
    )
    assert status_response.status_code == 200
    status_payload = status_response.get_json()
    assert status_payload["success"] is True
    assert status_payload["ok"] is True
    assert status_payload["status"] == ClassificationJob.STATUS_CANCELLED
    assert status_payload["is_complete"] is True

    with app.app_context():
        refreshed = db.session.get(ClassificationJob, job_id)
        assert refreshed is not None
        assert refreshed.status == ClassificationJob.STATUS_CANCELLED
        assert refreshed.completed_at is not None


def test_ai_classify_start_creates_new_job_when_previous_cancelled(client, app, monkeypatch):
    with app.app_context():
        user = _create_user("gate-ai-restart-cancelled@example.com")
        token = create_access_token(identity=str(user.id))

        block = Block(name="GI", user_id=user.id)
        db.session.add(block)
        db.session.flush()

        exam = PreviousExam(title="Physiology-2026-2", user_id=user.id)
        db.session.add(exam)
        db.session.flush()

        question = Question(
            exam_id=exam.id,
            user_id=user.id,
            question_number=1,
            content="Which cell secretes intrinsic factor?",
            q_type=Question.TYPE_MULTIPLE_CHOICE,
            answer="2",
            is_classified=False,
            lecture_id=None,
        )
        db.session.add(question)
        db.session.flush()
        question_id = question.id

        from app.routes.ai import _build_request_signature

        signature = _build_request_signature([question_id], None, None)
        cancelled_job = ClassificationJob(
            status=ClassificationJob.STATUS_CANCELLED,
            total_count=1,
            processed_count=0,
            success_count=0,
            failed_count=0,
            completed_at=datetime.utcnow(),
            result_json=json.dumps(
                {
                    "request": {
                        "signature": signature,
                        "question_ids": [question_id],
                    },
                    "results": [],
                }
            ),
        )
        db.session.add(cancelled_job)
        db.session.commit()
        cancelled_job_id = cancelled_job.id

    monkeypatch.setattr("app.routes.ai.GENAI_AVAILABLE", True)
    calls = []

    def fake_start_job(cls, question_ids, request_meta=None):
        calls.append({"question_ids": list(question_ids), "request_meta": request_meta or {}})
        job = ClassificationJob(
            status=ClassificationJob.STATUS_PENDING,
            total_count=len(question_ids),
            processed_count=0,
            success_count=0,
            failed_count=0,
            result_json=json.dumps({"request": request_meta or {}, "results": []}),
        )
        db.session.add(job)
        db.session.commit()
        return job.id

    monkeypatch.setattr(
        "app.routes.ai.AsyncBatchProcessor.start_classification_job",
        classmethod(fake_start_job),
    )

    response = client.post(
        "/ai/classify/start",
        headers=_auth_header(token),
        json={"question_ids": [question_id]},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["ok"] is True
    assert payload["reused"] is False
    assert payload["job_id"] != cancelled_job_id
    assert len(calls) == 1


def test_upload_lecture_material_indexes_in_api_manage(client, app, monkeypatch):
    with app.app_context():
        user = _create_user("gate-lecture-material@example.com")
        token = create_access_token(identity=str(user.id))

        block = Block(name="Neuro", user_id=user.id)
        db.session.add(block)
        db.session.flush()
        lecture = Lecture(block_id=block.id, title="Neuron", user_id=user.id, order=1)
        db.session.add(lecture)
        db.session.commit()
        lecture_id = lecture.id

    def fake_index_material(material, target_chars=1800, max_chars=2600):
        chunk = LectureChunk(
            lecture_id=material.lecture_id,
            material_id=material.id,
            page_start=1,
            page_end=1,
            content="mock chunk",
            char_len=10,
        )
        db.session.add(chunk)
        material.status = LectureMaterial.STATUS_INDEXED
        material.indexed_at = datetime.utcnow()
        db.session.add(material)
        db.session.commit()
        return {"chunks": 1, "pages": 1}

    monkeypatch.setattr("app.services.lecture_indexer.index_material", fake_index_material)

    response = client.post(
        f"/api/manage/lectures/{lecture_id}/materials",
        headers=_auth_header(token),
        data={"pdf_file": (BytesIO(b"%PDF-1.4 note"), "lecture_note.pdf")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["data"]["status"] == LectureMaterial.STATUS_INDEXED
    assert payload["data"]["chunks"] == 1
    assert payload["data"]["pages"] == 1

    with app.app_context():
        material = db.session.get(LectureMaterial, payload["data"]["materialId"])
        assert material is not None
        stored_path = Path(app.config["UPLOAD_FOLDER"]) / material.file_path
        assert not stored_path.exists()


def test_upload_lecture_material_keeps_pdf_when_enabled(client, app, monkeypatch):
    with app.app_context():
        user = _create_user("gate-lecture-material-keep@example.com")
        token = create_access_token(identity=str(user.id))

        block = Block(name="Neuro", user_id=user.id)
        db.session.add(block)
        db.session.flush()
        lecture = Lecture(block_id=block.id, title="Neuron", user_id=user.id, order=1)
        db.session.add(lecture)
        db.session.commit()
        lecture_id = lecture.id

    def fake_index_material(material, target_chars=1800, max_chars=2600):
        chunk = LectureChunk(
            lecture_id=material.lecture_id,
            material_id=material.id,
            page_start=1,
            page_end=1,
            content="mock chunk",
            char_len=10,
        )
        db.session.add(chunk)
        material.status = LectureMaterial.STATUS_INDEXED
        material.indexed_at = datetime.utcnow()
        db.session.add(material)
        db.session.commit()
        return {"chunks": 1, "pages": 1}

    monkeypatch.setattr("app.services.lecture_indexer.index_material", fake_index_material)

    old_keep = app.config.get("KEEP_PDF_AFTER_INDEX")
    app.config["KEEP_PDF_AFTER_INDEX"] = True
    try:
        response = client.post(
            f"/api/manage/lectures/{lecture_id}/materials",
            headers=_auth_header(token),
            data={"pdf_file": (BytesIO(b"%PDF-1.4 note"), "lecture_note.pdf")},
            content_type="multipart/form-data",
        )
    finally:
        app.config["KEEP_PDF_AFTER_INDEX"] = old_keep

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["data"]["status"] == LectureMaterial.STATUS_INDEXED

    with app.app_context():
        material = db.session.get(LectureMaterial, payload["data"]["materialId"])
        assert material is not None
        stored_path = Path(app.config["UPLOAD_FOLDER"]) / material.file_path
        assert stored_path.exists()
