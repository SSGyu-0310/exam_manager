from flask_jwt_extended import create_access_token

from app import db
from app.models import Block, Lecture, PreviousExam, Question, User


def _create_user(email, password="pw", is_admin=False):
    user = User(email=email, is_admin=is_admin)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def _token_for(user):
    return create_access_token(identity=str(user.id))


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def test_unclassified_api_returns_block_lectures(client, app):
    with app.app_context():
        user = _create_user("queue@example.com")
        block = Block(name="Block A", user_id=user.id)
        db.session.add(block)
        db.session.flush()
        lecture = Lecture(block_id=block.id, title="Lecture A", user_id=user.id)
        db.session.add(lecture)
        exam = PreviousExam(title="Exam A", user_id=user.id)
        db.session.add(exam)
        db.session.flush()
        question = Question(
            exam_id=exam.id,
            user_id=user.id,
            question_number=1,
            content="sample",
        )
        db.session.add(question)
        db.session.commit()
        token = _token_for(user)
        block_id = block.id
        lecture_payload = {"id": lecture.id, "title": lecture.title}

    response = client.get("/api/exam/unclassified", headers=_auth_header(token))
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True

    blocks = payload["data"]["blocks"]
    block_payload = next(item for item in blocks if item["id"] == block_id)
    assert "lectures" in block_payload
    assert block_payload["lectures"] == [lecture_payload]
