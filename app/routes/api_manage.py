"""JSON API for manage screens (blocks/lectures/exams)."""

from datetime import datetime

import os
import shutil
from pathlib import Path

from flask import Blueprint, request, jsonify, current_app, abort, url_for
from sqlalchemy import func, case
from sqlalchemy.orm import selectinload
from werkzeug.utils import secure_filename

from app import db
from app.models import (
    Block,
    Lecture,
    PreviousExam,
    Question,
    Choice,
    BlockFolder,
    LectureMaterial,
    LectureChunk,
    Subject,
)
from app.services.exam_cleanup import delete_exam_with_assets
from app.services.markdown_images import strip_markdown_images
from app.services.db_guard import guard_write_request
from app.services.block_sort import block_ordering
from app.services.user_scope import (
    attach_current_user,
    current_user,
    get_scoped_by_id,
    scope_model,
    scope_query,
)
from app.services.folder_scope import (
    parse_bool,
    resolve_folder_ids,
    resolve_lecture_ids,
    build_folder_tree,
)

api_manage_bp = Blueprint("api_manage", __name__, url_prefix="/api/manage")


@api_manage_bp.before_request
def restrict_to_local_admin():
    if not current_app.config.get("LOCAL_ADMIN_ONLY"):
        return None
    remote_addr = request.remote_addr or ""
    if remote_addr not in {"127.0.0.1", "::1"}:
        abort(404)
    return None


@api_manage_bp.before_request
def attach_user():
    return attach_current_user(require=True)


@api_manage_bp.before_request
def guard_read_only():
    blocked = guard_write_request()
    if blocked is not None:
        return blocked
    return None


def ok(data=None, status=200):
    return jsonify({"ok": True, "data": data}), status


def error_response(message, code="BAD_REQUEST", status=400, details=None):
    payload = {"ok": False, "code": code, "message": message}
    if details is not None:
        payload["details"] = details
    return jsonify(payload), status


def _build_block_counts(block_ids, user):
    if not block_ids:
        return {}, {}
    lecture_rows = (
        scope_query(Lecture.query, Lecture, user, include_public=True)
        .with_entities(Lecture.block_id, func.count(Lecture.id))
        .filter(Lecture.block_id.in_(block_ids))
        .group_by(Lecture.block_id)
        .all()
    )
    lecture_counts = {block_id: int(count or 0) for block_id, count in lecture_rows}
    question_rows = (
        scope_query(Question.query, Question, user)
        .join(Lecture, Question.lecture_id == Lecture.id)
        .with_entities(Lecture.block_id, func.count(Question.id))
        .filter(Lecture.block_id.in_(block_ids))
        .group_by(Lecture.block_id)
        .all()
    )
    question_counts = {block_id: int(count or 0) for block_id, count in question_rows}
    return lecture_counts, question_counts


def _build_lecture_counts(lecture_ids, user):
    if not lecture_ids:
        return {}, {}
    rows = (
        scope_query(Question.query, Question, user)
        .with_entities(
            Question.lecture_id,
            func.count(Question.id),
            func.sum(case((Question.is_classified.is_(True), 1), else_=0)),
        )
        .filter(Question.lecture_id.in_(lecture_ids))
        .group_by(Question.lecture_id)
        .all()
    )
    question_counts = {}
    classified_counts = {}
    for lecture_id, total, classified in rows:
        question_counts[lecture_id] = int(total or 0)
        classified_counts[lecture_id] = int(classified or 0)
    return question_counts, classified_counts


def _build_exam_counts(exam_ids, user):
    if not exam_ids:
        return {}
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
    counts = {}
    for exam_id, total, classified in rows:
        total_count = int(total or 0)
        classified_count = int(classified or 0)
        counts[exam_id] = {
            "total": total_count,
            "classified": classified_count,
            "unclassified": max(total_count - classified_count, 0),
        }
    return counts


def _build_choices_map(question_ids):
    if not question_ids:
        return {}
    choices = (
        Choice.query.filter(Choice.question_id.in_(question_ids))
        .order_by(Choice.question_id, Choice.choice_number)
        .all()
    )
    choices_by_question = {}
    for choice in choices:
        choices_by_question.setdefault(choice.question_id, []).append(choice)
    return choices_by_question


def _ensure_editable(resource, user, message):
    if resource and resource.user_id is None and not getattr(user, "is_admin", False):
        return error_response(message, code="FORBIDDEN", status=403)
    return None


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def _format_date(value):
    return value.isoformat() if value else None


def _parse_year(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _resolve_upload_folder() -> Path:
    upload_folder = current_app.config.get("UPLOAD_FOLDER")
    if not upload_folder:
        upload_folder = Path(current_app.static_folder) / "uploads"
    return Path(upload_folder)


def _compose_exam_title(subject=None, year=None, term=None, fallback=None):
    parts = []
    if subject:
        subject_text = str(subject).strip()
        if subject_text:
            parts.append(subject_text)
    year_value = _parse_year(year)
    if year_value:
        parts.append(str(year_value))
    if term:
        term_text = str(term).strip()
        if term_text:
            parts.append(term_text)
    title = "-".join(parts).strip()
    if title:
        return title
    if fallback:
        fallback_text = str(fallback).strip()
        if fallback_text:
            return fallback_text
    return None


def _block_payload(block, lecture_counts=None, question_counts=None):
    user = current_user()
    if lecture_counts is not None:
        lecture_count = lecture_counts.get(block.id, 0)
    else:
        lecture_count = (
            scope_query(Lecture.query, Lecture, user, include_public=True)
            .filter(Lecture.block_id == block.id)
            .count()
        )
    if question_counts is not None:
        question_count = question_counts.get(block.id, 0)
    else:
        question_count = (
            scope_query(Question.query, Question, user)
            .join(Lecture, Question.lecture_id == Lecture.id)
            .filter(Lecture.block_id == block.id)
            .count()
        )
    subject_name = block.subject_ref.name if block.subject_ref else block.subject
    return {
        "id": block.id,
        "name": block.name,
        "subject": subject_name,
        "subjectId": block.subject_id,
        "description": block.description,
        "order": block.order,
        "ownerId": block.user_id,
        "isPublic": block.user_id is None,
        "lectureCount": lecture_count,
        "questionCount": question_count,
        "createdAt": block.created_at.isoformat() if block.created_at else None,
        "updatedAt": block.updated_at.isoformat() if block.updated_at else None,
    }


def _lecture_payload(lecture, question_counts=None, classified_counts=None):
    user = current_user()
    if question_counts is not None and classified_counts is not None:
        question_count = question_counts.get(lecture.id, 0)
        classified_count = classified_counts.get(lecture.id, 0)
    else:
        question_query = scope_query(Question.query, Question, user).filter(
            Question.lecture_id == lecture.id
        )
        question_count = question_query.count()
        classified_count = question_query.filter_by(is_classified=True).count()
    return {
        "id": lecture.id,
        "blockId": lecture.block_id,
        "blockName": lecture.block.name if lecture.block else None,
        "blockSubject": (
            lecture.block.subject_ref.name
            if lecture.block and lecture.block.subject_ref
            else lecture.block.subject if lecture.block else None
        ),
        "folderId": lecture.folder_id,
        "title": lecture.title,
        "professor": lecture.professor,
        "order": lecture.order,
        "description": lecture.description,
        "ownerId": lecture.user_id,
        "isPublic": lecture.user_id is None,
        "questionCount": question_count,
        "classifiedCount": classified_count,
        "createdAt": lecture.created_at.isoformat() if lecture.created_at else None,
        "updatedAt": lecture.updated_at.isoformat() if lecture.updated_at else None,
    }


def _exam_payload(exam, exam_counts=None):
    if exam_counts is not None and exam.id in exam_counts:
        counts = exam_counts[exam.id]
        question_count = counts.get("total", 0)
        classified_count = counts.get("classified", 0)
        unclassified_count = counts.get("unclassified", 0)
    else:
        question_count = exam.question_count
        classified_count = exam.classified_count
        unclassified_count = exam.unclassified_count
    return {
        "id": exam.id,
        "title": exam.title,
        "examDate": _format_date(exam.exam_date),
        "subject": exam.subject,
        "year": exam.year,
        "term": exam.term,
        "description": exam.description,
        "questionCount": question_count,
        "classifiedCount": classified_count,
        "unclassifiedCount": unclassified_count,
        "createdAt": exam.created_at.isoformat() if exam.created_at else None,
        "updatedAt": exam.updated_at.isoformat() if exam.updated_at else None,
    }


def _folder_payload(folder):
    return {
        "id": folder.id,
        "blockId": folder.block_id,
        "parentId": folder.parent_id,
        "name": folder.name,
        "order": folder.order,
        "description": folder.description,
        "createdAt": folder.created_at.isoformat() if folder.created_at else None,
        "updatedAt": folder.updated_at.isoformat() if folder.updated_at else None,
    }


def _question_payload(question, choices_map=None):
    choices = None
    if choices_map is not None:
        choices = choices_map.get(question.id, [])
    return {
        "id": question.id,
        "questionNumber": question.question_number,
        "type": question.q_type,
        "examId": question.exam_id,
        "examTitle": question.exam.title if question.exam else None,
        "examiner": question.examiner,
        "lectureId": question.lecture_id,
        "lectureTitle": question.lecture.title if question.lecture else None,
        "isClassified": question.is_classified,
        "classificationStatus": question.classification_status,
        "hasImage": bool(question.image_path),
        "content": question.content,
        "choices": [
            _choice_payload(c)
            for c in (choices if choices is not None else question.choices.all())
        ]
        if (choices is not None or question.choices)
        else [],
    }


def _choice_payload(choice):
    return {
        "id": choice.id,
        "number": choice.choice_number,
        "content": choice.content,
        "imagePath": choice.image_path,
        "isCorrect": choice.is_correct,
    }


def _question_detail_payload(question):
    original_image_url = None
    try:
        from app.services.pdf_cropper import (
            find_question_crop_image,
            to_static_relative,
        )

        crop_path = find_question_crop_image(question.exam_id, question.question_number)
        if crop_path:
            relative_path = to_static_relative(
                crop_path, static_root=current_app.static_folder
            )
            if relative_path:
                original_image_url = url_for("static", filename=relative_path)
    except Exception:
        original_image_url = None
    return {
        "id": question.id,
        "examId": question.exam_id,
        "examTitle": question.exam.title if question.exam else None,
        "questionNumber": question.question_number,
        "examiner": question.examiner,
        "type": question.q_type,
        "lectureId": question.lecture_id,
        "lectureTitle": question.lecture.title if question.lecture else None,
        "content": question.content,
        "explanation": question.explanation,
        "imagePath": question.image_path,
        "originalImageUrl": original_image_url,
        "answer": question.answer,
        "correctAnswerText": question.correct_answer_text,
        "choices": [
            _choice_payload(choice)
            for choice in question.choices.order_by(Choice.choice_number)
        ],
    }


@api_manage_bp.get("/summary")
def manage_summary():
    user = current_user()
    block_query = scope_model(Block, user, include_public=True)
    lecture_query = scope_model(Lecture, user, include_public=True)
    exam_query = scope_model(PreviousExam, user)
    question_query = scope_model(Question, user)

    block_count = block_query.count()
    lecture_count = lecture_query.count()
    exam_count = exam_query.count()
    question_count = question_query.count()
    unclassified_count = question_query.filter_by(is_classified=False).count()
    recent_exams = exam_query.order_by(PreviousExam.created_at.desc()).limit(5).all()
    exam_counts = _build_exam_counts([exam.id for exam in recent_exams], user)

    return ok(
        {
            "counts": {
                "blocks": block_count,
                "lectures": lecture_count,
                "exams": exam_count,
                "questions": question_count,
                "unclassified": unclassified_count,
            },
            "recentExams": [_exam_payload(exam, exam_counts) for exam in recent_exams],
        }
    )


@api_manage_bp.get("/blocks")
def list_blocks():
    user = current_user()
    blocks = (
        scope_model(Block, user, include_public=True)
        .options(selectinload(Block.subject_ref))
        .order_by(*block_ordering())
        .all()
    )
    lecture_counts, question_counts = _build_block_counts([block.id for block in blocks], user)
    return ok([_block_payload(block, lecture_counts, question_counts) for block in blocks])


@api_manage_bp.get("/subjects")
def list_subjects():
    user = current_user()
    subjects = (
        scope_model(Subject, user, include_public=True)
        .order_by(Subject.order, Subject.name)
        .all()
    )
    return ok([_subject_payload(subject) for subject in subjects])


@api_manage_bp.post("/subjects")
def create_subject():
    user = current_user()
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    if not name:
        return error_response("Subject name is required.", code="SUBJECT_NAME_REQUIRED")

    raw_public = data.get("isPublic")
    if raw_public is None:
        is_public = bool(getattr(user, "is_admin", False))
    else:
        is_public = bool(raw_public)
    if is_public and not getattr(user, "is_admin", False):
        return error_response(
            "Public subjects require admin access.", code="FORBIDDEN", status=403
        )

    subject_name = str(name).strip()
    if not subject_name:
        return error_response("Subject name is required.", code="SUBJECT_NAME_REQUIRED")

    if is_public:
        subject = Subject.query.filter(
            Subject.user_id.is_(None), Subject.name == subject_name
        ).first()
    else:
        subject = Subject.query.filter(
            Subject.user_id == user.id, Subject.name == subject_name
        ).first()

    if subject:
        return ok(_subject_payload(subject))

    subject = Subject(
        name=subject_name,
        description=data.get("description"),
        order=int(data.get("order") or 0),
        user_id=None if is_public else user.id,
    )
    db.session.add(subject)
    db.session.commit()
    return ok(_subject_payload(subject), status=201)


@api_manage_bp.put("/subjects/<int:subject_id>")
def update_subject(subject_id):
    user = current_user()
    data = request.get_json(silent=True) or {}
    subject = get_scoped_by_id(Subject, subject_id, user, include_public=True)
    if not subject:
        return error_response("Subject not found.", code="SUBJECT_NOT_FOUND", status=404)
    edit_error = _ensure_editable(subject, user, "Public subjects are read-only.")
    if edit_error:
        return edit_error
    if "name" in data and data["name"] is not None:
        subject.name = str(data["name"])
    if "description" in data:
        subject.description = data.get("description")
    if "order" in data and data["order"] is not None:
        subject.order = int(data["order"])
    db.session.commit()
    return ok(_subject_payload(subject))


@api_manage_bp.post("/blocks")
def create_block():
    user = current_user()
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    if not name:
        return error_response("Block name is required.", code="BLOCK_NAME_REQUIRED")

    raw_public = data.get("isPublic")
    if raw_public is None:
        is_public = bool(getattr(user, "is_admin", False))
    else:
        is_public = bool(raw_public)
    if is_public and not getattr(user, "is_admin", False):
        return error_response(
            "Public blocks require admin access.", code="FORBIDDEN", status=403
        )

    block = Block(
        name=str(name),
        description=data.get("description"),
        order=int(data.get("order") or 0),
        user_id=None if is_public else user.id,
    )
    subject = _resolve_subject_from_payload(data, user, is_public)
    if subject:
        block.subject_id = subject.id
        block.subject = subject.name
    elif "subject" in data or "subjectId" in data:
        block.subject_id = None
        block.subject = None
    db.session.add(block)
    db.session.commit()
    return ok(_block_payload(block), status=201)


@api_manage_bp.get("/blocks/<int:block_id>")
def get_block(block_id):
    user = current_user()
    block = get_scoped_by_id(Block, block_id, user, include_public=True)
    if not block:
        return error_response("Block not found.", code="BLOCK_NOT_FOUND", status=404)
    lecture_counts, question_counts = _build_block_counts([block.id], user)
    return ok(_block_payload(block, lecture_counts, question_counts))


@api_manage_bp.get("/blocks/<int:block_id>/workspace")
def get_block_workspace(block_id):
    user = current_user()
    block = get_scoped_by_id(Block, block_id, user, include_public=True)
    if not block:
        return error_response("Block not found.", code="BLOCK_NOT_FOUND", status=404)
    folder_tree = build_folder_tree(block_id)

    folder_id = request.args.get("folderId") or request.args.get("folder_id")
    include_descendants = parse_bool(
        request.args.get("includeDescendants")
        or request.args.get("include_descendants"),
        True,
    )
    folder_id_value = None
    if folder_id:
        try:
            folder_id_value = int(folder_id)
        except ValueError:
            return error_response(
                "Invalid folder id.", code="INVALID_FOLDER_ID", status=400
            )

    lecture_ids = resolve_lecture_ids(
        block_id,
        folder_id_value,
        include_descendants,
        user=user,
        include_public=True,
    )
    lecture_query = scope_query(
        Lecture.query, Lecture, user, include_public=True
    ).filter(Lecture.block_id == block_id)
    lecture_query = lecture_query.options(
        selectinload(Lecture.block).selectinload(Block.subject_ref)
    )
    if lecture_ids is not None:
        if lecture_ids:
            lecture_query = lecture_query.filter(Lecture.id.in_(lecture_ids))
        else:
            lecture_query = lecture_query.filter(Lecture.id.is_(None))

    lectures = lecture_query.order_by(Lecture.order).all()

    subject = request.args.get("subject")
    exam_query = scope_query(PreviousExam.query, PreviousExam, user)
    if subject:
        exam_query = exam_query.filter(PreviousExam.subject == subject)
    exams = exam_query.order_by(PreviousExam.created_at.desc()).all()
    lecture_counts, classified_counts = _build_lecture_counts(
        [lecture.id for lecture in lectures], user
    )
    exam_counts = _build_exam_counts([exam.id for exam in exams], user)
    block_lecture_counts, block_question_counts = _build_block_counts([block.id], user)

    return ok(
        {
            "block": _block_payload(block, block_lecture_counts, block_question_counts),
            "folderTree": folder_tree,
            "lectures": [
                _lecture_payload(lecture, lecture_counts, classified_counts)
                for lecture in lectures
            ],
            "exams": [_exam_payload(exam, exam_counts) for exam in exams],
            "scope": {
                "blockId": block_id,
                "folderId": folder_id_value,
                "includeDescendants": include_descendants,
                "lectureIds": lecture_ids,
            },
        }
    )



@api_manage_bp.put("/blocks/<int:block_id>")
def update_block(block_id):
    user = current_user()
    data = request.get_json(silent=True) or {}
    block = get_scoped_by_id(Block, block_id, user, include_public=True)
    if not block:
        return error_response("Block not found.", code="BLOCK_NOT_FOUND", status=404)
    edit_error = _ensure_editable(block, user, "Public blocks are read-only.")
    if edit_error:
        return edit_error
    if "name" in data and data["name"] is not None:
        block.name = str(data["name"])
    if "subject" in data or "subjectId" in data:
        subject = _resolve_subject_from_payload(data, user, block.user_id is None)
        if subject:
            block.subject_id = subject.id
            block.subject = subject.name
        else:
            block.subject_id = None
            block.subject = None
    if "description" in data:
        block.description = data.get("description")
    if "order" in data and data["order"] is not None:
        block.order = int(data["order"])
    db.session.commit()
    return ok(_block_payload(block))


@api_manage_bp.delete("/blocks/<int:block_id>")
def delete_block(block_id):
    user = current_user()
    block = get_scoped_by_id(Block, block_id, user, include_public=True)
    if not block:
        return error_response("Block not found.", code="BLOCK_NOT_FOUND", status=404)
    edit_error = _ensure_editable(block, user, "Public blocks are read-only.")
    if edit_error:
        return edit_error
    fallback_block = _get_or_create_unassigned_block(user, block.user_id is None)
    Lecture.query.filter_by(block_id=block.id).update(
        {"block_id": fallback_block.id, "folder_id": None}
    )
    db.session.delete(block)
    db.session.commit()
    return ok({"id": block_id})


@api_manage_bp.get("/blocks/<int:block_id>/lectures")
def list_lectures(block_id):
    user = current_user()
    block = get_scoped_by_id(Block, block_id, user, include_public=True)
    if not block:
        return error_response("Block not found.", code="BLOCK_NOT_FOUND", status=404)
    folder_id = request.args.get("folderId") or request.args.get("folder_id")
    include_descendants = parse_bool(
        request.args.get("includeDescendants")
        or request.args.get("include_descendants"),
        True,
    )
    folder_id_value = None
    if folder_id:
        try:
            folder_id_value = int(folder_id)
        except ValueError:
            return error_response(
                "Invalid folder id.", code="INVALID_FOLDER_ID", status=400
            )

    lecture_ids = resolve_lecture_ids(
        block_id,
        folder_id_value,
        include_descendants,
        user=user,
        include_public=True,
    )
    query = scope_query(
        Lecture.query, Lecture, user, include_public=True
    ).filter(Lecture.block_id == block_id)
    query = query.options(selectinload(Lecture.block).selectinload(Block.subject_ref))
    if lecture_ids is not None:
        if lecture_ids:
            query = query.filter(Lecture.id.in_(lecture_ids))
        else:
            return ok(
                {
                    "block": _block_payload(block, *_build_block_counts([block.id], user)),
                    "lectures": [],
                    "scope": {
                        "blockId": block_id,
                        "folderId": folder_id_value,
                        "includeDescendants": include_descendants,
                        "lectureIds": [],
                    },
                }
            )
    lectures = query.order_by(Lecture.order).all()
    lecture_counts, classified_counts = _build_lecture_counts(
        [lecture.id for lecture in lectures], user
    )
    block_lecture_counts, block_question_counts = _build_block_counts([block.id], user)
    return ok(
        {
            "block": _block_payload(block, block_lecture_counts, block_question_counts),
            "lectures": [
                _lecture_payload(lecture, lecture_counts, classified_counts)
                for lecture in lectures
            ],
            "scope": {
                "blockId": block_id,
                "folderId": folder_id_value,
                "includeDescendants": include_descendants,
                "lectureIds": lecture_ids,
            },
        }
    )


@api_manage_bp.post("/blocks/<int:block_id>/lectures")
def create_lecture(block_id):
    user = current_user()
    block = get_scoped_by_id(Block, block_id, user, include_public=True)
    if not block:
        return error_response("Block not found.", code="BLOCK_NOT_FOUND", status=404)
    edit_error = _ensure_editable(block, user, "Public blocks are read-only.")
    if edit_error:
        return edit_error
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not title:
        return error_response(
            "Lecture title is required.", code="LECTURE_TITLE_REQUIRED"
        )

    folder_id = data.get("folderId") or data.get("folder_id")
    folder_id_value = None
    if folder_id is not None:
        try:
            folder_id_value = int(folder_id)
        except ValueError:
            return error_response("Invalid folder id.", code="INVALID_FOLDER_ID")
        folder = BlockFolder.query.get(folder_id_value)
        if not folder or folder.block_id != block_id:
            return error_response(
                "Folder not found.", code="FOLDER_NOT_FOUND", status=404
            )

    lecture_user_id = block.user_id if block.user_id is not None else None
    lecture = Lecture(
        block_id=block_id,
        folder_id=folder_id_value,
        title=str(title),
        professor=data.get("professor"),
        order=int(data.get("order") or 1),
        description=data.get("description"),
        user_id=lecture_user_id,
    )
    db.session.add(lecture)
    db.session.commit()
    return ok(_lecture_payload(lecture), status=201)


@api_manage_bp.get("/lectures/<int:lecture_id>")
def get_lecture(lecture_id):
    user = current_user()
    lecture = get_scoped_by_id(Lecture, lecture_id, user, include_public=True)
    if not lecture:
        return error_response("Lecture not found.", code="LECTURE_NOT_FOUND", status=404)
    return ok(_lecture_payload(lecture))


@api_manage_bp.get("/lectures/<int:lecture_id>/detail")
def get_lecture_detail(lecture_id):
    """Get lecture with classified questions and materials."""
    user = current_user()
    lecture = get_scoped_by_id(Lecture, lecture_id, user, include_public=True)
    if not lecture:
        return error_response("Lecture not found.", code="LECTURE_NOT_FOUND", status=404)

    # Get classified questions for this lecture
    questions = (
        scope_query(Question.query, Question, user)
        .options(selectinload(Question.exam))
        .filter(Question.lecture_id == lecture_id)
        .order_by(Question.question_number)
        .all()
    )
    choices_map = _build_choices_map([q.id for q in questions])

    # Get lecture materials (PDFs)
    materials = (
        LectureMaterial.query.filter_by(lecture_id=lecture_id)
        .order_by(LectureMaterial.uploaded_at.desc())
        .all()
    )
    material_ids = [material.id for material in materials]
    chunk_counts = {}
    if material_ids:
        chunk_rows = (
            db.session.query(LectureChunk.material_id, func.count(LectureChunk.id))
            .filter(LectureChunk.material_id.in_(material_ids))
            .group_by(LectureChunk.material_id)
            .all()
        )
        chunk_counts = {material_id: int(count or 0) for material_id, count in chunk_rows}

    materials_payload = []
    for material in materials:
        chunk_count = chunk_counts.get(material.id, 0)
        materials_payload.append({
            "id": material.id,
            "originalFilename": material.original_filename,
            "filePath": material.file_path,
            "status": material.status,
            "uploadedAt": material.uploaded_at.isoformat() if material.uploaded_at else None,
            "indexedAt": material.indexed_at.isoformat() if material.indexed_at else None,
            "chunks": chunk_count,
        })

    # Build question payloads with choices
    questions_payload = []
    for q in questions:
        q_payload = _question_payload(q, choices_map)
        q_payload["content"] = q.content
        q_payload["answer"] = q.answer
        q_payload["explanation"] = q.explanation
        q_payload["examTitle"] = q.exam.title if q.exam else None
        questions_payload.append(q_payload)

    lecture_counts, classified_counts = _build_lecture_counts([lecture.id], user)
    block_lecture_counts, block_question_counts = _build_block_counts([lecture.block_id], user)

    return ok({
        "lecture": _lecture_payload(lecture, lecture_counts, classified_counts),
        "block": _block_payload(lecture.block, block_lecture_counts, block_question_counts)
        if lecture.block
        else None,
        "questions": questions_payload,
        "materials": materials_payload,
    })


@api_manage_bp.post("/lectures/<int:lecture_id>/materials")
def upload_lecture_material(lecture_id):
    user = current_user()
    lecture = get_scoped_by_id(Lecture, lecture_id, user, include_public=True)
    if not lecture:
        return error_response("Lecture not found.", code="LECTURE_NOT_FOUND", status=404)
    edit_error = _ensure_editable(lecture, user, "Public lectures are read-only.")
    if edit_error:
        return edit_error

    if "pdf_file" not in request.files:
        return error_response("PDF file is required.", code="PDF_REQUIRED", status=400)

    file = request.files["pdf_file"]
    if file.filename == "":
        return error_response(
            "PDF filename is missing.", code="PDF_NAME_REQUIRED", status=400
        )
    if not file.filename.lower().endswith(".pdf"):
        return error_response(
            "Only PDF files are allowed.", code="PDF_INVALID_TYPE", status=400
        )

    upload_folder = _resolve_upload_folder()
    target_dir = upload_folder / "lecture_notes" / str(lecture.id)
    target_dir.mkdir(parents=True, exist_ok=True)

    original_name = Path(file.filename).name
    safe_name = secure_filename(original_name)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    stored_name = f"{timestamp}_{safe_name or 'lecture_note.pdf'}"
    stored_path = target_dir / stored_name
    material = None

    try:
        file.save(stored_path)

        relative_path = os.path.relpath(stored_path, upload_folder)
        relative_path = Path(relative_path).as_posix()

        material = LectureMaterial(
            lecture_id=lecture.id,
            file_path=relative_path,
            original_filename=original_name,
            status=LectureMaterial.STATUS_UPLOADED,
        )
        db.session.add(material)
        db.session.commit()

        from app.services.lecture_indexer import index_material

        index_result = index_material(material)
        chunk_count = LectureChunk.query.filter_by(material_id=material.id).count()
        return ok(
            {
                "materialId": material.id,
                "originalFilename": material.original_filename,
                "status": material.status,
                "chunks": chunk_count,
                "pages": index_result.get("pages", 0),
                "uploadedAt": material.uploaded_at.isoformat()
                if material.uploaded_at
                else None,
                "indexedAt": material.indexed_at.isoformat()
                if material.indexed_at
                else None,
            },
            status=201,
        )
    except Exception as exc:
        if material is None:
            db.session.rollback()
            try:
                stored_path.unlink(missing_ok=True)
            except OSError:
                current_app.logger.warning("Failed to cleanup %s", stored_path)
        current_app.logger.exception(
            "Lecture material upload/indexing failed for lecture_id=%s", lecture_id
        )
        return error_response(
            f"Lecture material indexing failed: {exc}",
            code="LECTURE_MATERIAL_INDEX_FAILED",
            status=500,
        )


@api_manage_bp.get("/lectures")
def list_all_lectures():
    user = current_user()
    lectures = (
        scope_model(Lecture, user, include_public=True)
        .options(selectinload(Lecture.block).selectinload(Block.subject_ref))
        .order_by(Lecture.order)
        .all()
    )
    lecture_counts, classified_counts = _build_lecture_counts(
        [lecture.id for lecture in lectures], user
    )
    return ok(
        [
            _lecture_payload(lecture, lecture_counts, classified_counts)
            for lecture in lectures
        ]
    )


@api_manage_bp.put("/lectures/<int:lecture_id>")
def update_lecture(lecture_id):
    user = current_user()
    lecture = get_scoped_by_id(Lecture, lecture_id, user, include_public=True)
    if not lecture:
        return error_response("Lecture not found.", code="LECTURE_NOT_FOUND", status=404)
    edit_error = _ensure_editable(lecture, user, "Public lectures are read-only.")
    if edit_error:
        return edit_error
    data = request.get_json(silent=True) or {}
    if "title" in data and data["title"] is not None:
        lecture.title = str(data["title"])
    if "professor" in data:
        lecture.professor = data.get("professor")
    if "order" in data and data["order"] is not None:
        lecture.order = int(data["order"])
    if "description" in data:
        lecture.description = data.get("description")
    if "folderId" in data or "folder_id" in data:
        folder_id = data.get("folderId") or data.get("folder_id")
        if folder_id is None:
            lecture.folder_id = None
        else:
            try:
                folder_id_value = int(folder_id)
            except ValueError:
                return error_response("Invalid folder id.", code="INVALID_FOLDER_ID")
            folder = BlockFolder.query.get(folder_id_value)
            if not folder or folder.block_id != lecture.block_id:
                return error_response(
                    "Folder not found.", code="FOLDER_NOT_FOUND", status=404
                )
            lecture.folder_id = folder_id_value
    if "isPublic" in data:
        desired_public = bool(data.get("isPublic"))
        if desired_public and not getattr(user, "is_admin", False):
            return error_response(
                "Public lectures require admin access.",
                code="FORBIDDEN",
                status=403,
            )
        if lecture.block and lecture.block.user_id is None and not desired_public:
            return error_response(
                "Move lecture to a custom block before making it private.",
                code="INVALID_SCOPE",
                status=400,
            )
        lecture.user_id = None if desired_public else user.id
    db.session.commit()
    return ok(_lecture_payload(lecture))


@api_manage_bp.delete("/lectures/<int:lecture_id>")
def delete_lecture(lecture_id):
    user = current_user()
    lecture = get_scoped_by_id(Lecture, lecture_id, user, include_public=True)
    if not lecture:
        return error_response("Lecture not found.", code="LECTURE_NOT_FOUND", status=404)
    edit_error = _ensure_editable(lecture, user, "Public lectures are read-only.")
    if edit_error:
        return edit_error
    db.session.delete(lecture)
    db.session.commit()
    return ok({"id": lecture_id})


@api_manage_bp.get("/exams")
def list_exams():
    user = current_user()
    exams = scope_model(PreviousExam, user).order_by(PreviousExam.exam_date.desc()).all()
    exam_counts = _build_exam_counts([exam.id for exam in exams], user)
    return ok([_exam_payload(exam, exam_counts) for exam in exams])


@api_manage_bp.post("/exams")
def create_exam():
    user = current_user()
    data = request.get_json(silent=True) or {}

    subject_value = (data.get("subject") or "").strip()
    term_value = (data.get("term") or "").strip()
    year_int = _parse_year(data.get("year"))
    title_input = (data.get("title") or "").strip()
    title = _compose_exam_title(
        subject=subject_value,
        year=year_int,
        term=term_value,
        fallback=title_input,
    )
    if not title:
        return error_response(
            "Exam title is required.",
            code="EXAM_TITLE_REQUIRED",
            status=400,
        )

    exam = PreviousExam(
        user_id=user.id,
        title=title,
        exam_date=_parse_date(data.get("examDate") or data.get("exam_date")),
        subject=subject_value or None,
        year=year_int,
        term=term_value or None,
        description=(data.get("description") or "").strip() or None,
        source_file=None,
    )
    db.session.add(exam)
    db.session.commit()
    return ok(_exam_payload(exam), status=201)


@api_manage_bp.post("/upload-pdf")
def upload_pdf():
    user = current_user()
    if "pdf_file" not in request.files:
        return error_response("PDF file is required.", code="PDF_REQUIRED", status=400)

    file = request.files["pdf_file"]
    if file.filename == "":
        return error_response(
            "PDF filename is missing.", code="PDF_NAME_REQUIRED", status=400
        )

    if not file.filename.lower().endswith(".pdf"):
        return error_response(
            "Only PDF files are allowed.", code="PDF_INVALID_TYPE", status=400
        )

    title_input = (request.form.get("title") or "").strip()
    subject_value = (request.form.get("subject") or "").strip()
    term_value = (request.form.get("term") or "").strip()
    year_value = request.form.get("year")
    year_int = _parse_year(year_value)

    title = _compose_exam_title(
        subject=subject_value,
        year=year_value,
        term=term_value,
        fallback=title_input,
    )
    if not title:
        return error_response(
            "Exam title could not be generated. Provide subject, year, and term.",
            code="EXAM_TITLE_REQUIRED",
            status=400,
        )
    if subject_value:
        subject = Subject.query.filter(
            Subject.user_id == user.id, Subject.name == subject_value
        ).first()
        if not subject:
            subject = Subject(name=subject_value, user_id=user.id)
            db.session.add(subject)
            db.session.flush()

    try:
        from app.services.pdf_parser_factory import parse_pdf

        parser_mode = current_app.config.get("PDF_PARSER_MODE", "legacy")
        tmp_path = None
        crop_dir = None
        crop_question_count = 0
        crop_image_count = 0
        crop_meta_url = None
        crop_question_images = {}
        crop_is_reliable = False
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        exam_prefix = secure_filename(title.replace(" ", "_"))[:20]
        upload_folder = current_app.config["UPLOAD_FOLDER"]
        questions_data = parse_pdf(
            tmp_path, upload_folder, exam_prefix, mode=parser_mode
        )
        if not questions_data:
            return error_response(
                "No questions extracted. Check PDF formatting.",
                code="PDF_PARSE_EMPTY",
                status=400,
            )

        exam = PreviousExam(
            title=title,
            subject=subject_value or None,
            year=year_int,
            term=term_value or None,
            source_file=secure_filename(file.filename),
            user_id=user.id,
        )
        db.session.add(exam)
        db.session.flush()

        from app.services.pdf_cropper import (
            crop_pdf_to_questions,
            get_exam_crop_dir,
            to_static_relative,
        )

        crop_dir = get_exam_crop_dir(exam.id, upload_folder)
        try:
            crop_result = crop_pdf_to_questions(
                tmp_path, exam.id, upload_folder=upload_folder
            )
            crop_meta = crop_result.get("meta") or {}
            crop_question_count = len(crop_meta.get("questions", []))
            crop_image_count = len(crop_result.get("question_images", {}))
            crop_question_images = crop_result.get("question_images", {}) or {}
            duplicate_qnums = crop_meta.get("duplicate_qnums") or []
            crop_is_reliable = (
                crop_question_count == len(questions_data)
                and crop_image_count == len(questions_data)
                and not duplicate_qnums
            )
            meta_path = crop_result.get("meta_path")
            if meta_path:
                relative_path = to_static_relative(
                    meta_path, static_root=current_app.static_folder
                )
                if relative_path:
                    crop_meta_url = url_for("static", filename=relative_path)
        except RuntimeError as exc:
            current_app.logger.warning("PDF crop skipped: %s", exc)

        question_count = 0
        choice_count = 0

        for q_data in questions_data:
            qnum = int(q_data["question_number"])
            # Keep parser output in question.image_path.
            # Cropped originals are exposed separately via originalImageUrl.
            question_image_path = q_data.get("image_path")

            answer_count = len(q_data.get("answer_options", []))
            has_options = len(q_data.get("options", [])) > 0

            if not has_options:
                q_type = Question.TYPE_SHORT_ANSWER
            elif answer_count > 1:
                q_type = Question.TYPE_MULTIPLE_RESPONSE
            else:
                q_type = Question.TYPE_MULTIPLE_CHOICE

            question = Question(
                exam_id=exam.id,
                user_id=user.id,
                question_number=qnum,
                content=q_data.get("content", ""),
                image_path=question_image_path,
                examiner=q_data.get("examiner"),
                q_type=q_type,
                answer=",".join(map(str, q_data.get("answer_options", []))),
                correct_answer_text=q_data.get("answer_text")
                if q_type == Question.TYPE_SHORT_ANSWER
                else None,
                explanation=q_data.get("answer_text")
                if q_type != Question.TYPE_SHORT_ANSWER
                else None,
                is_classified=False,
                lecture_id=None,
            )
            db.session.add(question)
            db.session.flush()

            for opt in q_data.get("options", []):
                if opt.get("content") or opt.get("image_path"):
                    choice = Choice(
                        question_id=question.id,
                        choice_number=opt["number"],
                        content=opt.get("content", ""),
                        image_path=opt.get("image_path"),
                        is_correct=opt.get("is_correct", False),
                    )
                    db.session.add(choice)
                    choice_count += 1

            question_count += 1

        db.session.commit()
        return ok(
            {
                "examId": exam.id,
                "questionCount": question_count,
                "choiceCount": choice_count,
                "cropImageCount": crop_image_count,
                "cropQuestionCount": crop_question_count,
                "cropReliable": crop_is_reliable,
                "cropMetaUrl": crop_meta_url,
            },
            status=201,
        )
    except ImportError as exc:
        db.session.rollback()
        if crop_dir:
            shutil.rmtree(crop_dir, ignore_errors=True)
        return error_response(
            f"PDF parser import failed: {exc}",
            code="PDF_PARSER_IMPORT",
            status=500,
        )
    except RuntimeError as exc:
        db.session.rollback()
        if crop_dir:
            shutil.rmtree(crop_dir, ignore_errors=True)
        return error_response(
            f"PDF crop error: {exc}",
            code="PDF_CROP_ERROR",
            status=500,
        )
    except Exception as exc:
        db.session.rollback()
        if crop_dir:
            shutil.rmtree(crop_dir, ignore_errors=True)
        return error_response(
            f"PDF parsing error: {exc}", code="PDF_PARSE_ERROR", status=500
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@api_manage_bp.get("/exams/<int:exam_id>")
def get_exam(exam_id):
    user = current_user()
    exam = get_scoped_by_id(PreviousExam, exam_id, user)
    if not exam:
        return error_response("Exam not found.", code="EXAM_NOT_FOUND", status=404)
    questions = (
        scope_query(Question.query, Question, user)
        .options(selectinload(Question.exam), selectinload(Question.lecture))
        .filter(Question.exam_id == exam.id)
        .order_by(Question.question_number)
        .all()
    )
    choices_map = _build_choices_map([q.id for q in questions])
    exam_counts = _build_exam_counts([exam.id], user)
    return ok(
        {
            "exam": _exam_payload(exam, exam_counts),
            "questions": [
                _question_payload(question, choices_map) for question in questions
            ],
        }
    )


@api_manage_bp.get("/questions/<int:question_id>")
def get_question(question_id):
    user = current_user()
    question = get_scoped_by_id(Question, question_id, user)
    if not question:
        return error_response(
            "Question not found.", code="QUESTION_NOT_FOUND", status=404
        )
    return ok(_question_detail_payload(question))


@api_manage_bp.put("/questions/<int:question_id>")
def update_question(question_id):
    user = current_user()
    question = get_scoped_by_id(Question, question_id, user)
    if not question:
        return error_response(
            "Question not found.", code="QUESTION_NOT_FOUND", status=404
        )
    data = request.get_json(silent=True) or {}

    raw_content = data.get("content") or ""
    uploaded_image = (data.get("uploadedImage") or "").strip()
    remove_image = bool(data.get("removeImage"))

    upload_folder = current_app.config.get("UPLOAD_FOLDER") or os.path.join(
        current_app.static_folder, "uploads"
    )
    upload_relative = (
        os.path.relpath(os.fspath(upload_folder), os.fspath(current_app.static_folder))
        .replace("\\", "/")
        .strip("/")
    )
    if upload_relative == ".":
        upload_relative = ""

    if uploaded_image:
        cleaned_content, markdown_filename = strip_markdown_images(
            raw_content, upload_relative, keep_unmatched=False
        )
    else:
        cleaned_content, markdown_filename = strip_markdown_images(
            raw_content, upload_relative, keep_unmatched=True
        )

    question.content = cleaned_content
    question.explanation = data.get("explanation") or ""
    if "examiner" in data:
        examiner = (data.get("examiner") or "").strip()
        question.examiner = examiner or None
    q_type = data.get("type") or question.q_type
    question.q_type = q_type

    if uploaded_image:
        question.image_path = uploaded_image
    elif remove_image:
        question.image_path = None
    elif markdown_filename:
        question.image_path = markdown_filename

    if "lectureId" in data:
        lecture_id = data.get("lectureId")
        if lecture_id:
            lecture = get_scoped_by_id(
                Lecture, int(lecture_id), user, include_public=True
            )
            if lecture:
                question.classify(lecture.id)
            else:
                return error_response(
                    "Lecture not found.", code="LECTURE_NOT_FOUND", status=404
                )
        else:
            question.unclassify()

    if q_type == Question.TYPE_SHORT_ANSWER:
        correct_text = data.get("correctAnswerText") or ""
        question.correct_answer_text = correct_text
        question.answer = correct_text
        for choice in question.choices.all():
            db.session.delete(choice)
    else:
        choices_payload = data.get("choices") or []
        correct_numbers = []
        for choice in choices_payload:
            if choice.get("isCorrect"):
                correct_numbers.append(str(choice.get("number")))
        question.answer = ",".join(correct_numbers)
        question.correct_answer_text = None
        for choice in question.choices.all():
            db.session.delete(choice)
        db.session.flush()
        for choice in choices_payload:
            content = choice.get("content", "")
            if content is None:
                content = ""
            new_choice = Choice(
                question_id=question.id,
                choice_number=int(choice.get("number") or 0),
                content=content,
                image_path=choice.get("imagePath"),
                is_correct=bool(choice.get("isCorrect")),
            )
            db.session.add(new_choice)

    db.session.commit()
    return ok(_question_detail_payload(question))


@api_manage_bp.put("/exams/<int:exam_id>")
def update_exam(exam_id):
    user = current_user()
    exam = get_scoped_by_id(PreviousExam, exam_id, user)
    if not exam:
        return error_response("Exam not found.", code="EXAM_NOT_FOUND", status=404)
    data = request.get_json(silent=True) or {}
    title_input = data.get("title") if "title" in data else None
    if "examDate" in data or "exam_date" in data:
        exam.exam_date = _parse_date(data.get("examDate") or data.get("exam_date"))
    if "subject" in data:
        exam.subject = data.get("subject")
    if "year" in data:
        exam.year = _parse_year(data.get("year"))
    if "term" in data:
        exam.term = data.get("term")
    if "description" in data:
        exam.description = data.get("description")
    if {"subject", "year", "term", "title"} & data.keys():
        computed_title = _compose_exam_title(
            subject=exam.subject,
            year=exam.year,
            term=exam.term,
            fallback=title_input,
        )
        if computed_title:
            exam.title = computed_title
    db.session.commit()
    return ok(_exam_payload(exam))


@api_manage_bp.delete("/exams/<int:exam_id>")
def delete_exam(exam_id):
    user = current_user()
    exam = get_scoped_by_id(PreviousExam, exam_id, user)
    if not exam:
        return error_response("Exam not found.", code="EXAM_NOT_FOUND", status=404)
    delete_exam_with_assets(exam)
    return ok({"id": exam_id})
def _subject_payload(subject):
    return {
        "id": subject.id,
        "name": subject.name,
        "order": subject.order,
        "description": subject.description,
        "ownerId": subject.user_id,
        "isPublic": subject.user_id is None,
        "createdAt": subject.created_at.isoformat() if subject.created_at else None,
        "updatedAt": subject.updated_at.isoformat() if subject.updated_at else None,
    }


def _resolve_subject_from_payload(data, user, is_public):
    subject_id = data.get("subjectId") if isinstance(data, dict) else None
    subject_name = (data.get("subject") if isinstance(data, dict) else None) or ""
    subject_name = subject_name.strip()

    if subject_id:
        subject = get_scoped_by_id(Subject, int(subject_id), user, include_public=not is_public)
        return subject

    if not subject_name:
        return None

    if is_public:
        subject = Subject.query.filter(
            Subject.user_id.is_(None), Subject.name == subject_name
        ).first()
    else:
        subject = Subject.query.filter(
            Subject.user_id == user.id, Subject.name == subject_name
        ).first()

    if not subject:
        subject = Subject(
            name=subject_name,
            user_id=None if is_public else user.id,
        )
        db.session.add(subject)
        db.session.flush()

    return subject


def _get_or_create_unassigned_block(user, is_public):
    fallback_name = "미지정"
    query = Block.query.filter(Block.name == fallback_name, Block.subject.is_(None))
    if is_public:
        query = query.filter(Block.user_id.is_(None))
    else:
        query = query.filter(Block.user_id == user.id)
    block = query.first()
    if block:
        return block
    block = Block(
        name=fallback_name,
        subject=None,
        subject_id=None,
        description=None,
        order=0,
        user_id=None if is_public else user.id,
    )
    db.session.add(block)
    db.session.flush()
    return block
