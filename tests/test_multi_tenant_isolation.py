from flask_jwt_extended import create_access_token

from app import db
from app.models import User, Block, Lecture, PreviousExam


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


def _create_exam(user, title):
    exam = PreviousExam(title=title, user_id=user.id)
    db.session.add(exam)
    db.session.commit()
    return exam


def test_unauthenticated_requests_are_rejected(client):
    response = client.get("/api/manage/summary")
    assert response.status_code == 401


def test_user_a_sees_only_own_exams(client, app):
    with app.app_context():
        user_a = _create_user("a@example.com")
        user_b = _create_user("b@example.com")
        _create_exam(user_a, "Exam A")
        _create_exam(user_b, "Exam B")
        token_a = _token_for(user_a)

    response = client.get("/api/manage/exams", headers=_auth_header(token_a))
    assert response.status_code == 200
    payload = response.get_json()
    titles = {exam["title"] for exam in payload["data"]}
    assert titles == {"Exam A"}


def test_user_b_does_not_see_user_a_exams(client, app):
    with app.app_context():
        user_a = _create_user("a2@example.com")
        user_b = _create_user("b2@example.com")
        _create_exam(user_a, "Exam A2")
        _create_exam(user_b, "Exam B2")
        token_b = _token_for(user_b)

    response = client.get("/api/manage/exams", headers=_auth_header(token_b))
    assert response.status_code == 200
    payload = response.get_json()
    titles = {exam["title"] for exam in payload["data"]}
    assert titles == {"Exam B2"}


def test_direct_id_access_is_blocked(client, app):
    with app.app_context():
        user_a = _create_user("a3@example.com")
        user_b = _create_user("b3@example.com")
        exam_id = _create_exam(user_a, "Exam A3").id
        token_b = _token_for(user_b)

    response = client.get(
        f"/api/manage/exams/{exam_id}", headers=_auth_header(token_b)
    )
    assert response.status_code in (403, 404)


def test_user_id_payload_is_ignored(client, app):
    with app.app_context():
        user_a = _create_user("a4@example.com")
        token_a = _token_for(user_a)

    response = client.post(
        "/api/manage/exams",
        headers=_auth_header(token_a),
        json={"title": "Exam A4", "user_id": 999},
    )
    assert response.status_code == 201
    payload = response.get_json()
    exam_id = payload["data"]["id"]

    with app.app_context():
        exam = PreviousExam.query.get(exam_id)
        assert exam.user_id == user_a.id


def test_public_lectures_visible_private_hidden(client, app):
    with app.app_context():
        user_a = _create_user("a5@example.com")
        user_b = _create_user("b5@example.com")
        block_public = Block(name="Public", user_id=None)
        block_private = Block(name="Private", user_id=user_a.id)
        db.session.add_all([block_public, block_private])
        db.session.flush()
        lecture_public = Lecture(
            block_id=block_public.id, title="Public Lecture", user_id=None
        )
        lecture_private = Lecture(
            block_id=block_private.id, title="Private Lecture", user_id=user_a.id
        )
        db.session.add_all([lecture_public, lecture_private])
        db.session.commit()
        token_b = _token_for(user_b)

    response = client.get("/api/manage/lectures", headers=_auth_header(token_b))
    assert response.status_code == 200
    payload = response.get_json()
    titles = {lecture["title"] for lecture in payload["data"]}
    assert "Public Lecture" in titles
    assert "Private Lecture" not in titles
