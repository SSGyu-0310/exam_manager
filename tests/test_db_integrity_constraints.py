from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

from app import db
from app.models import (
    Block,
    ClassificationJob,
    Lecture,
    LectureChunk,
    LectureMaterial,
    PreviousExam,
    Question,
    QuestionChunkMatch,
)


def _seed_question_chunk_match_dependencies():
    block = Block(name="Integrity Block")
    db.session.add(block)
    db.session.flush()

    lecture = Lecture(block_id=block.id, title="Integrity Lecture", order=1)
    exam = PreviousExam(title="Integrity Exam")
    db.session.add_all([lecture, exam])
    db.session.flush()

    question = Question(
        exam_id=exam.id,
        question_number=1,
        content="Integrity question",
        q_type=Question.TYPE_MULTIPLE_CHOICE,
        is_classified=False,
    )
    material = LectureMaterial(
        lecture_id=lecture.id,
        file_path="materials/integrity.pdf",
    )
    db.session.add_all([question, material])
    db.session.flush()

    chunk = LectureChunk(
        lecture_id=lecture.id,
        material_id=material.id,
        page_start=1,
        page_end=1,
        content="chunk snippet",
    )
    job = ClassificationJob(
        status=ClassificationJob.STATUS_PENDING,
        total_count=1,
        processed_count=0,
        success_count=0,
        failed_count=0,
    )
    db.session.add_all([chunk, job])
    db.session.commit()
    return question, lecture, chunk, job


def test_questions_unique_exam_question_number_allows_distinct_exams(app):
    with app.app_context():
        exam1 = PreviousExam(title="Exam 1")
        exam2 = PreviousExam(title="Exam 2")
        db.session.add_all([exam1, exam2])
        db.session.flush()

        db.session.add_all(
            [
                Question(
                    exam_id=exam1.id,
                    question_number=1,
                    content="Q1",
                    q_type=Question.TYPE_MULTIPLE_CHOICE,
                ),
                Question(
                    exam_id=exam2.id,
                    question_number=1,
                    content="Q1-duplicate-number-different-exam",
                    q_type=Question.TYPE_MULTIPLE_CHOICE,
                ),
            ]
        )
        db.session.commit()


def test_questions_unique_exam_question_number_blocks_duplicates(app):
    with app.app_context():
        exam = PreviousExam(title="Unique Exam")
        db.session.add(exam)
        db.session.flush()

        db.session.add_all(
            [
                Question(
                    exam_id=exam.id,
                    question_number=7,
                    content="Q7-A",
                    q_type=Question.TYPE_MULTIPLE_CHOICE,
                ),
                Question(
                    exam_id=exam.id,
                    question_number=7,
                    content="Q7-B",
                    q_type=Question.TYPE_MULTIPLE_CHOICE,
                ),
            ]
        )

        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_questions_reject_invalid_exam_fk(app):
    with app.app_context():
        db.session.add(
            Question(
                exam_id=999999,
                question_number=1,
                content="invalid exam fk",
                q_type=Question.TYPE_MULTIPLE_CHOICE,
            )
        )

        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_question_chunk_matches_unique_question_chunk_source_blocks_duplicates(app):
    with app.app_context():
        question, lecture, chunk, job = _seed_question_chunk_match_dependencies()
        db.session.add_all(
            [
                QuestionChunkMatch(
                    question_id=question.id,
                    lecture_id=lecture.id,
                    chunk_id=chunk.id,
                    material_id=chunk.material_id,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    snippet="same chunk evidence #1",
                    source="ai",
                    job_id=job.id,
                    is_primary=True,
                ),
                QuestionChunkMatch(
                    question_id=question.id,
                    lecture_id=lecture.id,
                    chunk_id=chunk.id,
                    material_id=chunk.material_id,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    snippet="same chunk evidence #2",
                    source="ai",
                    job_id=job.id,
                    is_primary=False,
                ),
            ]
        )

        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_question_chunk_matches_valid_insert_succeeds(app):
    with app.app_context():
        question, lecture, chunk, job = _seed_question_chunk_match_dependencies()
        match = QuestionChunkMatch(
            question_id=question.id,
            lecture_id=lecture.id,
            chunk_id=chunk.id,
            material_id=chunk.material_id,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            snippet="valid evidence",
            source="ai",
            job_id=job.id,
            is_primary=True,
        )
        db.session.add(match)
        db.session.commit()
        assert match.id is not None


def test_question_chunk_matches_rejects_invalid_foreign_keys(app):
    with app.app_context():
        _, lecture, chunk, job = _seed_question_chunk_match_dependencies()
        db.session.add(
            QuestionChunkMatch(
                question_id=999999,
                lecture_id=lecture.id,
                chunk_id=chunk.id,
                material_id=chunk.material_id,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                snippet="invalid fk",
                source="ai",
                job_id=job.id,
                is_primary=False,
            )
        )

        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_question_chunk_matches_rejects_null_source(app):
    with app.app_context():
        question, lecture, chunk, job = _seed_question_chunk_match_dependencies()
        with pytest.raises(IntegrityError):
            db.session.execute(
                text(
                    """
                    INSERT INTO question_chunk_matches (
                        question_id,
                        lecture_id,
                        chunk_id,
                        material_id,
                        page_start,
                        page_end,
                        snippet,
                        source,
                        job_id,
                        is_primary,
                        created_at
                    ) VALUES (
                        :question_id,
                        :lecture_id,
                        :chunk_id,
                        :material_id,
                        :page_start,
                        :page_end,
                        :snippet,
                        NULL,
                        :job_id,
                        FALSE,
                        NOW()
                    )
                    """
                ),
                {
                    "question_id": question.id,
                    "lecture_id": lecture.id,
                    "chunk_id": chunk.id,
                    "material_id": chunk.material_id,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "snippet": "null source",
                    "job_id": job.id,
                },
            )
            db.session.commit()
        db.session.rollback()


def test_classification_jobs_not_null_and_defaults(app):
    with app.app_context():
        valid = ClassificationJob()
        db.session.add(valid)
        db.session.commit()
        assert valid.status == ClassificationJob.STATUS_PENDING
        assert valid.total_count == 0
        assert valid.processed_count == 0
        assert valid.success_count == 0
        assert valid.failed_count == 0

        with pytest.raises(IntegrityError):
            db.session.execute(
                text(
                    """
                    INSERT INTO classification_jobs (
                        status,
                        total_count,
                        processed_count,
                        success_count,
                        failed_count,
                        created_at,
                        updated_at
                    ) VALUES (
                        NULL,
                        0,
                        0,
                        0,
                        0,
                        NOW(),
                        NOW()
                    )
                    """
                )
            )
            db.session.commit()
        db.session.rollback()
