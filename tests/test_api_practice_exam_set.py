from flask_jwt_extended import create_access_token

from app import db
from app.models import Choice, PracticeSession, PracticeAnswer, PreviousExam, Question, User


def _create_user(email: str, password: str = "pw") -> User:
    user = User(email=email, is_admin=False)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token(identity=str(user.id))
    return {"Authorization": f"Bearer {token}"}


def _create_exam_with_question(user: User, title: str, qnum: int, correct_choice: int):
    exam = PreviousExam(title=title, user_id=user.id)
    db.session.add(exam)
    db.session.flush()

    question = Question(
        exam_id=exam.id,
        user_id=user.id,
        question_number=qnum,
        content=f"{title} question {qnum}",
    )
    db.session.add(question)
    db.session.flush()

    choices = []
    for idx in range(1, 5):
        choice = Choice(
            question_id=question.id,
            choice_number=idx,
            content=f"choice {idx}",
            is_correct=(idx == correct_choice),
        )
        choices.append(choice)
    db.session.add_all(choices)
    db.session.commit()
    return exam, question


def test_exam_set_flow_create_questions_submit_and_result(client, app):
    with app.app_context():
        user = _create_user("practice-exam-set@example.com")
        exam_a, question_a = _create_exam_with_question(user, "Exam A", 1, 2)
        exam_b, question_b = _create_exam_with_question(user, "Exam B", 1, 3)
        exam_a_id = exam_a.id
        exam_b_id = exam_b.id
        question_a_id = question_a.id
        question_b_id = question_b.id
        headers = _auth_header(user)

    create_response = client.post(
        "/api/practice/sessions",
        json={"mode": "exam_practice", "examIds": [exam_a_id, exam_b_id]},
        headers=headers,
    )
    assert create_response.status_code == 200
    created = create_response.get_json()
    assert created["sessionId"]
    assert created["examIds"] == [exam_a_id, exam_b_id]
    assert len(created["questionOrder"]) == 2

    list_response = client.get(
        f"/api/practice/exam-set/questions?exam_ids={exam_a_id}&exam_ids={exam_b_id}",
        headers=headers,
    )
    assert list_response.status_code == 200
    listed = list_response.get_json()
    assert listed["examIds"] == [exam_a_id, exam_b_id]
    assert listed["total"] == 2
    assert [item["questionId"] for item in listed["questions"]] == [
        question_a_id,
        question_b_id,
    ]

    submit_response = client.post(
        f"/api/practice/sessions/{created['sessionId']}/submit",
        json={
            "version": 1,
            "answers": {
                str(question_a_id): {"type": "mcq", "value": [2]},
                str(question_b_id): {"type": "mcq", "value": [1]},
            },
        },
        headers=headers,
    )
    assert submit_response.status_code == 200
    submitted = submit_response.get_json()
    assert submitted["sessionId"] == created["sessionId"]
    assert submitted["summary"]["all"]["total"] == 2
    assert submitted["summary"]["all"]["answered"] == 2
    assert submitted["summary"]["all"]["correct"] == 1

    result_response = client.get(
        f"/api/practice/exam-set/result?exam_ids={exam_a_id}&exam_ids={exam_b_id}&includeAnswer=true",
        headers=headers,
    )
    assert result_response.status_code == 200
    result = result_response.get_json()
    assert result["examIds"] == [exam_a_id, exam_b_id]
    assert result["total"] == 2
    assert len(result["questions"]) == 2
    assert "correctChoiceNumbers" in result["questions"][0]


def test_exam_questions_hide_crop_image_from_primary_image_url(client, app):
    with app.app_context():
        user = _create_user("practice-exam-crop-visibility@example.com")
        headers = _auth_header(user)

        exam = PreviousExam(title="Exam With Crop", user_id=user.id)
        db.session.add(exam)
        db.session.flush()
        exam_id = exam.id

        question = Question(
            exam_id=exam_id,
            user_id=user.id,
            question_number=1,
            content="Question with crop source",
            image_path=f"exam_crops/exam_{exam_id}/Q01.png",
        )
        db.session.add(question)
        db.session.flush()

        choice = Choice(
            question_id=question.id,
            choice_number=1,
            content="Choice with inline image",
            image_path="inline_choice.png",
            is_correct=True,
        )
        db.session.add(choice)
        db.session.commit()

    response = client.get(
        f"/api/practice/exam/{exam_id}/questions",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["total"] == 1
    item = payload["questions"][0]
    assert item["imageUrl"] is None
    assert item["originalImageUrl"] == f"/static/uploads/exam_crops/exam_{exam_id}/Q01.png"
    assert item["choices"][0]["imageUrl"] == "/static/uploads/inline_choice.png"


def test_session_progress_save_and_restore(client, app):
    """PATCH progress saves draft answers and currentQuestionIndex, restorable via GET detail."""
    with app.app_context():
        user = _create_user("progress-save@example.com")
        exam, question = _create_exam_with_question(user, "Exam Progress", 1, 2)
        exam_id = exam.id
        question_id = question.id
        headers = _auth_header(user)

    # Create session
    create_resp = client.post(
        "/api/practice/sessions",
        json={"mode": "exam_practice", "examIds": [exam_id]},
        headers=headers,
    )
    assert create_resp.status_code == 200
    session_id = create_resp.get_json()["sessionId"]

    # Save progress
    progress_resp = client.patch(
        f"/api/practice/sessions/{session_id}/progress",
        json={
            "currentQuestionIndex": 3,
            "answers": {
                str(question_id): {"type": "mcq", "value": [1]},
            },
            "elapsedSeconds": 42,
        },
        headers=headers,
    )
    assert progress_resp.status_code == 200
    progress_data = progress_resp.get_json()
    assert progress_data["ok"] is True
    assert progress_data["currentQuestionIndex"] == 3

    # Verify via session detail
    detail_resp = client.get(
        f"/api/practice/sessions/{session_id}",
        headers=headers,
    )
    assert detail_resp.status_code == 200
    detail = detail_resp.get_json()
    assert detail["currentQuestionIndex"] == 3
    assert detail["finishedAt"] is None
    # Check draft answer is present
    items = detail["items"]
    assert len(items) == 1
    assert items[0]["questionId"] == question_id
    assert items[0]["isAnswered"] is True
    assert items[0]["answer"]["type"] == "mcq"
    assert items[0]["answer"]["value"] == [1]
    # is_correct should be None (draft, not graded)
    assert items[0]["isCorrect"] is None

    # After progress save, submit should still work
    submit_resp = client.post(
        f"/api/practice/sessions/{session_id}/submit",
        json={
            "version": 1,
            "answers": {
                str(question_id): {"type": "mcq", "value": [2]},
            },
        },
        headers=headers,
    )
    assert submit_resp.status_code == 200
    submitted = submit_resp.get_json()
    assert submitted["summary"]["all"]["correct"] == 1


def test_session_progress_rejects_finished(client, app):
    """PATCH progress should be rejected for already-finished sessions."""
    with app.app_context():
        user = _create_user("progress-finished@example.com")
        exam, question = _create_exam_with_question(user, "Exam Finished", 1, 2)
        exam_id = exam.id
        question_id = question.id
        headers = _auth_header(user)

    # Create and submit session
    create_resp = client.post(
        "/api/practice/sessions",
        json={"mode": "exam_practice", "examIds": [exam_id]},
        headers=headers,
    )
    session_id = create_resp.get_json()["sessionId"]

    client.post(
        f"/api/practice/sessions/{session_id}/submit",
        json={
            "version": 1,
            "answers": {str(question_id): {"type": "mcq", "value": [2]}},
        },
        headers=headers,
    )

    # Try to save progress on finished session
    progress_resp = client.patch(
        f"/api/practice/sessions/{session_id}/progress",
        json={"currentQuestionIndex": 0},
        headers=headers,
    )
    assert progress_resp.status_code == 400
    assert progress_resp.get_json()["code"] == "SESSION_FINISHED"


def test_session_progress_clears_deleted_answers(client, app):
    """PATCH progress should remove answers not present in latest draft payload."""
    with app.app_context():
        user = _create_user("progress-clear@example.com")
        exam, question = _create_exam_with_question(user, "Exam Clear", 1, 2)
        exam_id = exam.id
        question_id = question.id
        headers = _auth_header(user)

    create_resp = client.post(
        "/api/practice/sessions",
        json={"mode": "exam_practice", "examIds": [exam_id]},
        headers=headers,
    )
    assert create_resp.status_code == 200
    session_id = create_resp.get_json()["sessionId"]

    first_save_resp = client.patch(
        f"/api/practice/sessions/{session_id}/progress",
        json={"answers": {str(question_id): {"type": "mcq", "value": [1]}}},
        headers=headers,
    )
    assert first_save_resp.status_code == 200

    clear_resp = client.patch(
        f"/api/practice/sessions/{session_id}/progress",
        json={"answers": {}},
        headers=headers,
    )
    assert clear_resp.status_code == 200

    detail_resp = client.get(
        f"/api/practice/sessions/{session_id}",
        headers=headers,
    )
    assert detail_resp.status_code == 200
    detail = detail_resp.get_json()
    assert detail["answeredCount"] == 0
    assert len(detail["items"]) == 1
    assert detail["items"][0]["questionId"] == question_id
    assert detail["items"][0]["isAnswered"] is False
    assert detail["items"][0]["answer"] is None
