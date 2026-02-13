"""Manage service for admin operations (blocks/lectures/exams).

This service centralizes management operations for blocks, lectures, and exams.
Routes should delegate to these functions rather than implementing business logic.
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func, case

from app import db
from app.models import Block, Lecture, PreviousExam, Question, Choice
from app.services.markdown_images import strip_markdown_images
from app.services.user_scope import scope_model, scope_query


def get_dashboard_stats(user) -> dict:
    """Get dashboard statistics."""
    exam_query = scope_model(PreviousExam, user)

    question_stats = scope_query(
        db.session.query(
            func.count(Question.id).label("question_count"),
            func.sum(case((Question.is_classified.is_(False), 1), else_=0)).label(
                "unclassified_count"
            ),
        ),
        Question,
        user,
    ).subquery()

    counts_row = db.session.query(
        scope_model(Block, user, include_public=True)
        .with_entities(func.count(Block.id))
        .scalar_subquery()
        .label("block_count"),
        scope_model(Lecture, user, include_public=True)
        .with_entities(func.count(Lecture.id))
        .scalar_subquery()
        .label("lecture_count"),
        exam_query.with_entities(func.count(PreviousExam.id))
        .scalar_subquery()
        .label("exam_count"),
        func.coalesce(question_stats.c.question_count, 0).label("question_count"),
        func.coalesce(question_stats.c.unclassified_count, 0).label(
            "unclassified_count"
        ),
    ).one()

    recent_exams = exam_query.order_by(PreviousExam.created_at.desc()).limit(5).all()
    exam_ids = [exam.id for exam in recent_exams]
    exam_counts = {}
    if exam_ids:
        rows = (
            scope_query(Question.query, Question, user)
            .with_entities(
                Question.exam_id,
                func.count(Question.id),
                func.sum(case((Question.is_classified.is_(True), 1), else_=0)),
            )
            .filter(Question.exam_id.in_(exam_ids))
            .group_by(Question.exam_id)
            .all()
        )
        for exam_id, total, classified in rows:
            total_count = int(total or 0)
            classified_count = int(classified or 0)
            exam_counts[exam_id] = {
                "total": total_count,
                "unclassified": max(total_count - classified_count, 0),
            }
    return {
        "block_count": int(counts_row.block_count or 0),
        "lecture_count": int(counts_row.lecture_count or 0),
        "exam_count": int(counts_row.exam_count or 0),
        "question_count": int(counts_row.question_count or 0),
        "unclassified_count": int(counts_row.unclassified_count or 0),
        "recent_exams": [
            {
                "id": e.id,
                "title": e.title,
                "subject": e.subject,
                "year": e.year,
                "term": e.term,
                "question_count": exam_counts.get(e.id, {}).get("total", 0),
                "unclassified_count": exam_counts.get(e.id, {}).get("unclassified", 0),
            }
            for e in recent_exams
        ],
    }


def get_block_details(block_id: int) -> Optional[dict]:
    """Get block details with related data."""
    block = db.session.get(Block, block_id)
    if not block:
        return None

    return {
        "id": block.id,
        "name": block.name,
        "description": block.description,
        "order": block.order,
        "lecture_count": block.lecture_count,
        "question_count": block.question_count,
        "created_at": block.created_at.isoformat() if block.created_at else None,
        "updated_at": block.updated_at.isoformat() if block.updated_at else None,
    }


def create_block(name: str, description: str, order: int) -> Block:
    """Create a new block."""
    block = Block(name=name, description=description, order=order)
    db.session.add(block)
    db.session.commit()
    return block


def update_block(
    block_id: int, name: str, description: str, order: int
) -> Optional[Block]:
    """Update an existing block."""
    block = db.session.get(Block, block_id)
    if not block:
        return None
    block.name = name
    block.description = description
    block.order = order
    db.session.commit()
    return block


def delete_block(block_id: int) -> bool:
    """Delete a block."""
    block = db.session.get(Block, block_id)
    if not block:
        return False
    fallback_block = _get_or_create_unassigned_block(block.user_id)
    Lecture.query.filter_by(block_id=block.id).update(
        {"block_id": fallback_block.id, "folder_id": None}
    )
    db.session.delete(block)
    db.session.commit()
    return True


def _get_or_create_unassigned_block(user_id: Optional[int]):
    fallback_name = "미지정"
    query = Block.query.filter(Block.name == fallback_name, Block.subject.is_(None))
    if user_id is None:
        query = query.filter(Block.user_id.is_(None))
    else:
        query = query.filter(Block.user_id == user_id)
    block = query.first()
    if block:
        return block
    block = Block(
        name=fallback_name,
        subject=None,
        subject_id=None,
        description=None,
        order=0,
        user_id=user_id,
    )
    db.session.add(block)
    db.session.flush()
    return block


def get_lecture_details(lecture_id: int) -> Optional[dict]:
    """Get lecture details with related data."""
    lecture = db.session.get(Lecture, lecture_id)
    if not lecture:
        return None

    return {
        "id": lecture.id,
        "block_id": lecture.block_id,
        "folder_id": lecture.folder_id,
        "parent_id": None,  # legacy key kept for compatibility
        "name": lecture.title,  # legacy key kept for compatibility
        "title": lecture.title,
        "order": lecture.order,
        "description": lecture.description,
        "professor": lecture.professor,
        "question_count": lecture.question_count,
        "created_at": lecture.created_at.isoformat() if lecture.created_at else None,
        "updated_at": lecture.updated_at.isoformat() if lecture.updated_at else None,
    }


def create_lecture(
    block_id: int,
    folder_id: Optional[int],
    parent_id: Optional[int],
    name: str,
    order: int,
    description: str,
    professor: Optional[str],
    user_id: Optional[int] = None,
) -> Lecture:
    """Create a new lecture."""
    lecture = Lecture(
        block_id=block_id,
        folder_id=folder_id,
        title=name,
        order=order,
        description=description,
        professor=professor,
        user_id=user_id,
    )
    db.session.add(lecture)
    db.session.commit()
    return lecture


def update_lecture(
    lecture_id: int,
    block_id: int,
    folder_id: Optional[int],
    parent_id: Optional[int],
    name: str,
    order: int,
    description: str,
    professor: Optional[str],
) -> Optional[Lecture]:
    """Update an existing lecture."""
    lecture = db.session.get(Lecture, lecture_id)
    if not lecture:
        return None
    lecture.block_id = block_id
    lecture.folder_id = folder_id
    lecture.title = name
    lecture.order = order
    lecture.description = description
    lecture.professor = professor
    db.session.commit()
    return lecture


def delete_lecture(lecture_id: int) -> bool:
    """Delete a lecture."""
    lecture = db.session.get(Lecture, lecture_id)
    if not lecture:
        return False
    db.session.delete(lecture)
    db.session.commit()
    return True



def get_question_details(question_id: int) -> Optional[dict]:
    """Get question details with choices."""
    question = db.session.get(Question, question_id)
    if not question:
        return None

    return {
        "id": question.id,
        "exam_id": question.exam_id,
        "number": question.question_number,
        "question_number": question.question_number,
        "question_text": question.content,
        "content": question.content,
        "choices": [
            {
                "id": c.id,
                "text": c.content,
                "content": c.content,
                "number": c.choice_number,
                "is_correct": c.is_correct,
            }
            for c in question.choices.order_by(Choice.choice_number).all()
        ],
        "explanation": question.explanation,
        "is_classified": question.is_classified,
        "lecture_id": question.lecture_id,
        "question_type": question.q_type,
        "q_type": question.q_type,
        "image_url": question.image_path,
        "image_path": question.image_path,
        "created_at": question.created_at.isoformat() if question.created_at else None,
        "updated_at": question.updated_at.isoformat() if question.updated_at else None,
    }


def update_question(
    question_id: int,
    question_text: str,
    explanation: str,
    is_classified: bool,
    lecture_id: Optional[int],
    question_type: Optional[str],
) -> Optional[Question]:
    """Update a question."""
    question = db.session.get(Question, question_id)
    if not question:
        return None
    question.content = question_text
    question.explanation = explanation
    question.is_classified = is_classified
    question.lecture_id = lecture_id
    question.q_type = question_type
    db.session.commit()
    return question


def update_question_choices(
    question_id: int,
    choices_data: List[dict],
) -> Optional[Question]:
    """Update question choices."""
    question = db.session.get(Question, question_id)
    if not question:
        return None

    Choice.query.filter_by(question_id=question_id).delete(synchronize_session=False)

    for idx, choice_data in enumerate(choices_data, start=1):
        choice_number = choice_data.get("number")
        if choice_number is None:
            choice_number = choice_data.get("choice_number", idx)
        choice_content = choice_data.get("content")
        if choice_content is None:
            choice_content = choice_data.get("text", "")
        choice = Choice(
            question_id=question_id,
            choice_number=int(choice_number),
            content=choice_content,
            image_path=choice_data.get("image_path"),
            is_correct=choice_data.get("is_correct", False),
        )
        db.session.add(choice)

    db.session.commit()
    return question


def delete_question(question_id: int) -> bool:
    """Delete a question."""
    question = db.session.get(Question, question_id)
    if not question:
        return False
    db.session.delete(question)
    db.session.commit()
    return True


def process_question_markdown(
    question_id: int,
    markdown_content: str,
    upload_folder: Optional[str],
) -> tuple[str, Optional[str]]:
    """Process markdown content for a question and extract image filename."""
    from app.services.file_paths import get_upload_folder

    if upload_folder is None:
        upload_folder = get_upload_folder()
    else:
        upload_folder = get_upload_folder(admin="admin" in upload_folder)

    return strip_markdown_images(markdown_content, upload_folder)
