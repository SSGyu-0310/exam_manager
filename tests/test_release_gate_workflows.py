from __future__ import annotations

import json
from datetime import datetime
from io import BytesIO

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
        exam = PreviousExam.query.get(exam_id)
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
        lambda question_ids, job_id, apply_mode="all": len(question_ids),
    )

    start_response = client.post(
        "/ai/classify/start",
        headers=_auth_header(token),
        json={"question_ids": [question_id]},
    )
    assert start_response.status_code == 200
    start_payload = start_response.get_json()
    assert start_payload["success"] is True
    job_id = start_payload["job_id"]

    status_response = client.get(
        f"/ai/classify/status/{job_id}", headers=_auth_header(token)
    )
    assert status_response.status_code == 200
    status_payload = status_response.get_json()
    assert status_payload["success"] is True
    assert status_payload["status"] == ClassificationJob.STATUS_COMPLETED
    assert status_payload["is_complete"] is True

    result_response = client.get(
        f"/ai/classify/result/{job_id}", headers=_auth_header(token)
    )
    assert result_response.status_code == 200
    result_payload = result_response.get_json()
    assert result_payload["success"] is True
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
    assert apply_payload["applied_count"] == 1


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
