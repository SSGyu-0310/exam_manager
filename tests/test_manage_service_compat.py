from __future__ import annotations

from app import db
from app.models import Block, Choice, PreviousExam, Question, User
from app.services import manage_service


def _create_user(email: str) -> User:
    user = User(email=email)
    user.set_password("pw")
    db.session.add(user)
    db.session.commit()
    return user


def test_create_and_update_lecture_use_title_field(app):
    with app.app_context():
        user = _create_user("manage-service-lecture@example.com")
        block = Block(name="Block A", user_id=user.id)
        db.session.add(block)
        db.session.commit()

        lecture = manage_service.create_lecture(
            block_id=block.id,
            folder_id=None,
            parent_id=999,  # legacy arg should be ignored safely
            name="Intro",
            order=1,
            description="desc",
            professor="Prof",
            user_id=user.id,
        )

        assert lecture.title == "Intro"
        details = manage_service.get_lecture_details(lecture.id)
        assert details is not None
        assert details["name"] == "Intro"
        assert details["title"] == "Intro"
        assert details["parent_id"] is None

        updated = manage_service.update_lecture(
            lecture_id=lecture.id,
            block_id=block.id,
            folder_id=None,
            parent_id=123,  # legacy arg should be ignored safely
            name="Updated Intro",
            order=2,
            description="desc2",
            professor="Prof2",
        )
        assert updated is not None
        assert updated.title == "Updated Intro"


def test_question_detail_and_choice_update_are_schema_compatible(app):
    with app.app_context():
        user = _create_user("manage-service-question@example.com")
        exam = PreviousExam(title="Exam A", user_id=user.id)
        db.session.add(exam)
        db.session.flush()
        question = Question(
            exam_id=exam.id,
            user_id=user.id,
            question_number=1,
            content="Q1",
            q_type=Question.TYPE_MULTIPLE_CHOICE,
            answer="1",
        )
        db.session.add(question)
        db.session.commit()

        updated = manage_service.update_question(
            question_id=question.id,
            question_text="Updated Q1",
            explanation="exp",
            is_classified=False,
            lecture_id=None,
            question_type=Question.TYPE_MULTIPLE_CHOICE,
        )
        assert updated is not None
        assert updated.content == "Updated Q1"

        manage_service.update_question_choices(
            question_id=question.id,
            choices_data=[
                {"number": 1, "text": "A", "is_correct": True},
                {"choice_number": 2, "content": "B", "is_correct": False},
            ],
        )

        rows = (
            Choice.query.filter_by(question_id=question.id)
            .order_by(Choice.choice_number)
            .all()
        )
        assert [c.choice_number for c in rows] == [1, 2]
        assert [c.content for c in rows] == ["A", "B"]

        details = manage_service.get_question_details(question.id)
        assert details is not None
        assert details["question_text"] == "Updated Q1"
        assert details["content"] == "Updated Q1"
        assert details["question_type"] == Question.TYPE_MULTIPLE_CHOICE
        assert details["image_path"] is None
