import json
import os
from datetime import datetime

from flask import Blueprint, jsonify, request, current_app, url_for
from sqlalchemy import func

from app import db
from app.models import (
    Block,
    Lecture,
    Question,
    Choice,
    PracticeSession,
    PracticeAnswer,
    PreviousExam,
)
from app.services.practice_service import (
    build_question_groups,
    evaluate_practice_answers,
    get_exam_questions_ordered,
    get_exam_set_questions_ordered,
    get_lecture_questions_ordered,
    grade_exam_set_submission,
    grade_exam_submission,
    grade_practice_submission,
    normalize_practice_answers_payload,
)
from app.services.practice_filters import (
    parse_exam_filter_args,
    apply_exam_filter,
    build_exam_options,
)
from app.services.db_guard import guard_write_request
from app.services.transaction import transaction
from app.services.user_scope import (
    attach_current_user,
    current_user,
    get_scoped_by_id,
    scope_model,
    scope_query,
)
from app.services.block_sort import block_ordering

api_practice_bp = Blueprint("api_practice", __name__)


@api_practice_bp.before_request
def guard_read_only():
    blocked = guard_write_request()
    if blocked is not None:
        return blocked
    return None


@api_practice_bp.before_request
def attach_user():
    return attach_current_user(require=True)


def error_response(message, code, status=400, details=None):
    payload = {"ok": False, "code": code, "message": message}
    if details is not None:
        payload["details"] = details
    return jsonify(payload), status


def _build_upload_url(image_path):
    if not image_path:
        return None
    if isinstance(image_path, str):
        normalized = image_path.strip()
        if not normalized:
            return None
        if normalized.startswith(("http://", "https://")):
            return normalized
        normalized = normalized.lstrip("/")
        if normalized.startswith("static/"):
            normalized = normalized[len("static/") :]
            return url_for("static", filename=normalized)
        upload_folder = current_app.config.get("UPLOAD_FOLDER") or os.path.join(
            current_app.static_folder, "uploads"
        )
        relative_folder = os.path.relpath(
            os.fspath(upload_folder), os.fspath(current_app.static_folder)
        )
        relative_folder = relative_folder.replace("\\", "/").strip("/")
        if relative_folder == ".":
            relative_folder = ""
        if relative_folder and normalized.startswith(f"{relative_folder}/"):
            return url_for("static", filename=normalized)
        if relative_folder:
            return url_for("static", filename=f"{relative_folder}/{normalized}")
        return url_for("static", filename=normalized)
    return None


def _format_datetime(value):
    if value is None:
        return None
    return value.replace(microsecond=0).isoformat() + "Z"


def _parse_pagination_args():
    limit_param = request.args.get("limit")
    offset_param = request.args.get("offset")
    limit = None
    offset = 0

    if offset_param is not None:
        if not offset_param.isdigit():
            return None, None, ("Invalid offset.", "INVALID_PAYLOAD")
        offset = int(offset_param)
        if offset < 0:
            return None, None, ("Invalid offset.", "INVALID_PAYLOAD")

    if limit_param is not None:
        if not limit_param.isdigit():
            return None, None, ("Invalid limit.", "INVALID_PAYLOAD")
        limit = int(limit_param)
        if limit <= 0:
            return None, None, ("Invalid limit.", "INVALID_PAYLOAD")

    return limit, offset, None


def _load_choices_for_questions(question_ids):
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


def _load_session_question_order(session):
    if not session.question_order:
        return []
    try:
        order = json.loads(session.question_order)
    except (TypeError, ValueError):
        return []
    if not isinstance(order, list):
        return []
    normalized = []
    for item in order:
        try:
            normalized.append(int(item))
        except (TypeError, ValueError):
            continue
    return normalized


def _load_session_scope_ids(session):
    if not session.lecture_ids_json:
        return []
    try:
        raw = json.loads(session.lecture_ids_json)
    except (TypeError, ValueError):
        return []
    if not isinstance(raw, list):
        return []

    scope_ids = []
    seen = set()
    for item in raw:
        try:
            value = int(item)
        except (TypeError, ValueError):
            continue
        if value in seen:
            continue
        seen.add(value)
        scope_ids.append(value)
    return scope_ids


def _load_session_allowed_question_ids(session, user):
    question_order = _load_session_question_order(session)
    if question_order:
        return {str(question_id) for question_id in question_order}

    question_user_id = None if getattr(user, "is_admin", False) else user.id
    if session.lecture_id:
        questions = (
            get_lecture_questions_ordered(session.lecture_id, user_id=question_user_id)
            or []
        )
        return {str(question.id) for question in questions}

    scoped_exam_ids = _load_session_scope_ids(session)
    if scoped_exam_ids:
        questions = (
            get_exam_set_questions_ordered(scoped_exam_ids, user_id=question_user_id)
            or []
        )
        return {str(question.id) for question in questions}

    return set()


def _parse_answer_payload(value):
    if not value:
        return None
    if isinstance(value, dict):
        return value
    try:
        payload = json.loads(value)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _normalize_exam_ids(raw_values):
    exam_ids = []
    seen = set()

    def _append(raw):
        if raw is None:
            return
        if isinstance(raw, (list, tuple, set)):
            for item in raw:
                _append(item)
            return
        for part in str(raw).split(","):
            token = part.strip()
            if not token or not token.isdigit():
                continue
            exam_id = int(token)
            if exam_id in seen:
                continue
            seen.add(exam_id)
            exam_ids.append(exam_id)

    _append(raw_values)
    return exam_ids


def _extract_exam_ids(data=None):
    query_ids = _normalize_exam_ids(request.args.getlist("exam_ids"))
    if not isinstance(data, dict):
        return query_ids

    payload_ids = []
    if "examIds" in data:
        payload_ids = _normalize_exam_ids(data.get("examIds"))
    elif "exam_ids" in data:
        payload_ids = _normalize_exam_ids(data.get("exam_ids"))

    return payload_ids or query_ids


def _resolve_scoped_exams(exam_ids, user):
    if not exam_ids:
        return [], []

    exams = (
        scope_query(PreviousExam.query, PreviousExam, user)
        .filter(PreviousExam.id.in_(exam_ids))
        .all()
    )
    exam_map = {exam.id: exam for exam in exams}
    missing_ids = [exam_id for exam_id in exam_ids if exam_id not in exam_map]
    ordered_exams = [exam_map[exam_id] for exam_id in exam_ids if exam_id in exam_map]
    return ordered_exams, missing_ids


def _compose_exam_set_title(exams):
    if not exams:
        return "Selected exams"
    if len(exams) == 1:
        return exams[0].title
    first_title = exams[0].title
    return f"{first_title} +{len(exams) - 1}"


def _resolve_question_crop_image_url(question):
    if not getattr(question, "exam_id", None):
        return None
    if not getattr(question, "question_number", None):
        return None

    try:
        from app.services.pdf_cropper import find_question_crop_image, to_static_relative

        crop_path = find_question_crop_image(question.exam_id, question.question_number)
        if not crop_path:
            return None
        relative_path = to_static_relative(
            crop_path, static_root=current_app.static_folder
        )
        if not relative_path:
            return None
        return url_for("static", filename=relative_path)
    except Exception:
        return None


def _build_question_payload(question, choices_by_question, include_answer=False):
    choices = choices_by_question.get(question.id, [])

    raw_image_path = (question.image_path or "").strip()
    image_url = None
    if raw_image_path and not raw_image_path.startswith("exam_crops/"):
        image_url = _build_upload_url(raw_image_path)

    original_image_url = _resolve_question_crop_image_url(question)
    if original_image_url is None and raw_image_path.startswith("exam_crops/"):
        original_image_url = _build_upload_url(raw_image_path)

    payload = {
        "questionId": question.id,
        "stem": question.content or "",
        "choices": [
            {
                "number": choice.choice_number,
                "content": choice.content,
                "imageUrl": _build_upload_url(choice.image_path),
            }
            for choice in choices
        ],
        "isShortAnswer": question.is_short_answer,
        "isMultipleResponse": question.is_multiple_response,
        "examId": question.exam_id,
        "examTitle": question.exam.title if question.exam else None,
        "imageUrl": image_url,
        "originalImageUrl": original_image_url,
    }
    if include_answer:
        payload["explanation"] = question.explanation
        if question.is_short_answer:
            payload["correctAnswerText"] = question.correct_answer_text
        else:
            payload["correctChoiceNumbers"] = [
                choice.choice_number for choice in choices if choice.is_correct
            ]
    return payload


@api_practice_bp.route("/lectures")
def list_lectures():
    user = current_user()
    blocks = (
        scope_model(Block, user, include_public=True).order_by(*block_ordering()).all()
    )
    lectures = (
        scope_model(Lecture, user, include_public=True)
        .order_by(Lecture.block_id, Lecture.order)
        .all()
    )
    lecture_ids = [lecture.id for lecture in lectures]
    question_counts = {}
    if lecture_ids:
        count_rows = (
            scope_query(Question.query, Question, user)
            .with_entities(Question.lecture_id, func.count(Question.id))
            .filter(Question.lecture_id.in_(lecture_ids))
            .group_by(Question.lecture_id)
            .all()
        )
        question_counts = {
            lecture_id: int(count or 0) for lecture_id, count in count_rows
        }
    lectures_by_block = {}
    for lecture in lectures:
        lectures_by_block.setdefault(lecture.block_id, []).append(lecture)

    blocks_payload = []
    for block in blocks:
        block_lectures = lectures_by_block.get(block.id, [])
        lectures_payload = [
            {
                "lectureId": lecture.id,
                "title": lecture.title,
                "order": lecture.order,
                "questionCount": question_counts.get(lecture.id, 0),
            }
            for lecture in block_lectures
        ]
        blocks_payload.append(
            {
                "blockId": block.id,
                "title": block.name,
                "lectures": lectures_payload,
            }
        )

    return jsonify({"blocks": blocks_payload})


@api_practice_bp.route("/lecture/<int:lecture_id>")
def lecture_questions(lecture_id):
    user = current_user()
    lecture = get_scoped_by_id(Lecture, lecture_id, user, include_public=True)
    if lecture is None:
        return error_response("Lecture not found.", "LECTURE_NOT_FOUND", 404)

    exam_ids, filter_active = parse_exam_filter_args(request.args)
    question_user_id = None if getattr(user, "is_admin", False) else user.id
    all_questions = (
        get_lecture_questions_ordered(lecture_id, user_id=question_user_id) or []
    )
    exam_options = build_exam_options(all_questions)
    questions = apply_exam_filter(all_questions, exam_ids, filter_active)
    groups = build_question_groups(questions)
    question_meta = groups["question_meta"]
    question_map = {question.id: question for question in questions}
    selected_exam_ids = (
        exam_ids if filter_active else [option["id"] for option in exam_options]
    )

    questions_payload = []
    for meta in question_meta:
        question = question_map.get(meta["id"])
        exam = question.exam if question else None
        questions_payload.append(
            {
                "questionId": meta["id"],
                "originalSeq": meta["original_seq"],
                "typeSeq": meta["type_seq"],
                "type": meta["type"],
                "isShortAnswer": meta["is_short_answer"],
                "isMultipleResponse": meta["is_multiple_response"],
                "examId": question.exam_id if question else None,
                "examTitle": exam.title if exam else None,
            }
        )
    multiple_response_count = sum(
        1 for meta in question_meta if meta.get("is_multiple_response")
    )

    return jsonify(
        {
            "lectureId": lecture.id,
            "title": lecture.title,
            "questions": questions_payload,
            "totalCount": len(question_meta),
            "objectiveCount": len(groups["objective_questions"]),
            "subjectiveCount": len(groups["subjective_questions"]),
            "multipleResponseCount": multiple_response_count,
            "examOptions": exam_options,
            "selectedExamIds": selected_exam_ids,
            "filterActive": filter_active,
        }
    )


@api_practice_bp.route("/lecture/<int:lecture_id>/question/<int:question_id>")
def lecture_question(lecture_id, question_id):
    user = current_user()
    lecture = get_scoped_by_id(Lecture, lecture_id, user, include_public=True)
    if lecture is None:
        return error_response("Lecture not found.", "LECTURE_NOT_FOUND", 404)

    question = (
        scope_query(Question.query, Question, user)
        .filter_by(id=question_id, lecture_id=lecture_id)
        .first()
    )
    if question is None:
        return error_response(
            "Question not found in lecture.", "QUESTION_NOT_IN_LECTURE", 404
        )

    choices = question.choices.order_by(Choice.choice_number).all()
    payload = _build_question_payload(question, {question.id: choices})
    payload["hasExplanation"] = bool(question.explanation)
    return jsonify(payload)


@api_practice_bp.route("/lecture/<int:lecture_id>/questions")
def lecture_question_list(lecture_id):
    user = current_user()
    lecture = get_scoped_by_id(Lecture, lecture_id, user, include_public=True)
    if lecture is None:
        return error_response("Lecture not found.", "LECTURE_NOT_FOUND", 404)

    limit, offset, error = _parse_pagination_args()
    if error:
        message, code = error
        return error_response(message, code, 400)

    exam_ids, filter_active = parse_exam_filter_args(request.args)
    query = scope_query(Question.query, Question, user).filter_by(lecture_id=lecture_id)
    if filter_active:
        if not exam_ids:
            response_payload = {
                "lectureId": lecture.id,
                "title": lecture.title,
                "total": 0,
                "offset": offset,
                "questions": [],
            }
            if limit is not None:
                response_payload["limit"] = limit
            return jsonify(response_payload)
        query = query.filter(Question.exam_id.in_(exam_ids))
    query = query.order_by(Question.question_number)
    total = query.count()
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    questions = query.all()

    question_ids = [question.id for question in questions]
    choices_by_question = _load_choices_for_questions(question_ids)

    questions_payload = [
        _build_question_payload(question, choices_by_question) for question in questions
    ]

    response_payload = {
        "lectureId": lecture.id,
        "title": lecture.title,
        "total": total,
        "offset": offset,
        "questions": questions_payload,
    }
    if limit is not None:
        response_payload["limit"] = limit

    return jsonify(response_payload)


@api_practice_bp.route("/exam/<int:exam_id>/questions")
def exam_question_list(exam_id):
    user = current_user()
    exam = get_scoped_by_id(PreviousExam, exam_id, user)
    if exam is None:
        return error_response("Exam not found.", "EXAM_NOT_FOUND", 404)

    limit, offset, error = _parse_pagination_args()
    if error:
        message, code = error
        return error_response(message, code, 400)

    query = scope_query(Question.query, Question, user).filter_by(exam_id=exam_id)
    query = query.order_by(Question.question_number)
    total = query.count()
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    questions = query.all()

    question_ids = [question.id for question in questions]
    choices_by_question = _load_choices_for_questions(question_ids)

    questions_payload = [
        _build_question_payload(question, choices_by_question) for question in questions
    ]

    response_payload = {
        "examId": exam.id,
        "title": exam.title,
        "total": total,
        "offset": offset,
        "questions": questions_payload,
    }
    if limit is not None:
        response_payload["limit"] = limit

    return jsonify(response_payload)


@api_practice_bp.route("/exam-set/questions")
def exam_set_question_list():
    user = current_user()
    exam_ids = _extract_exam_ids()
    if not exam_ids:
        return error_response(
            "At least one exam id is required.", "EXAM_IDS_REQUIRED", 400
        )

    exams, missing_ids = _resolve_scoped_exams(exam_ids, user)
    if missing_ids:
        return error_response(
            "One or more exams were not found.",
            "EXAM_NOT_FOUND",
            404,
            details={"examIds": missing_ids},
        )

    limit, offset, error = _parse_pagination_args()
    if error:
        message, code = error
        return error_response(message, code, 400)

    question_user_id = None if getattr(user, "is_admin", False) else user.id
    ordered_questions = get_exam_set_questions_ordered(
        exam_ids, user_id=question_user_id
    )
    total = len(ordered_questions)
    start = int(offset or 0)
    end = None
    if limit is not None:
        end = start + int(limit)
    questions = ordered_questions[start:end]

    question_ids = [question.id for question in questions]
    choices_by_question = _load_choices_for_questions(question_ids)
    questions_payload = [
        _build_question_payload(question, choices_by_question) for question in questions
    ]

    response_payload = {
        "examIds": [exam.id for exam in exams],
        "title": _compose_exam_set_title(exams),
        "total": total,
        "offset": offset,
        "questions": questions_payload,
    }
    if limit is not None:
        response_payload["limit"] = limit
    return jsonify(response_payload)


@api_practice_bp.route("/lecture/<int:lecture_id>/submit", methods=["POST"])
def submit_answers(lecture_id):
    user = current_user()
    lecture = get_scoped_by_id(Lecture, lecture_id, user, include_public=True)
    if lecture is None:
        return error_response("Lecture not found.", "LECTURE_NOT_FOUND", 404)

    raw_body = request.get_data(cache=True, as_text=True)
    data = request.get_json(silent=True)
    if data is None:
        if raw_body:
            return error_response("Invalid JSON.", "INVALID_JSON", 400)
        return error_response("Invalid request payload.", "INVALID_PAYLOAD", 400)

    exam_ids, filter_active = parse_exam_filter_args(request.args)
    question_user_id = None if getattr(user, "is_admin", False) else user.id
    all_questions = (
        get_lecture_questions_ordered(lecture_id, user_id=question_user_id) or []
    )
    questions = apply_exam_filter(all_questions, exam_ids, filter_active)
    if filter_active and not questions:
        return error_response(
            "No questions for the selected exams.",
            "NO_QUESTIONS",
            400,
        )
    question_meta = {str(q.id): q.is_short_answer for q in questions}

    answers_v1, deprecated_input, error_code, error_message = (
        normalize_practice_answers_payload(data, question_meta)
    )
    if error_code:
        return error_response(error_message, error_code, 400)

    invalid_ids = [key for key in answers_v1.keys() if key not in question_meta]
    if invalid_ids:
        return error_response(
            "Question not in lecture.",
            "QUESTION_NOT_IN_LECTURE",
            400,
            details={"questionIds": invalid_ids},
        )

    summary, items = grade_practice_submission(lecture_id, answers_v1, user_id=user.id)
    submitted_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    return jsonify(
        {
            "lectureId": lecture.id,
            "submittedAt": submitted_at,
            "deprecatedInput": deprecated_input,
            "summary": summary,
            "items": items,
        }
    )


@api_practice_bp.route("/exam/<int:exam_id>/submit", methods=["POST"])
def submit_exam_answers(exam_id):
    user = current_user()
    exam = get_scoped_by_id(PreviousExam, exam_id, user)
    if exam is None:
        return error_response("Exam not found.", "EXAM_NOT_FOUND", 404)

    raw_body = request.get_data(cache=True, as_text=True)
    data = request.get_json(silent=True)
    if data is None:
        if raw_body:
            return error_response("Invalid JSON.", "INVALID_JSON", 400)
        return error_response("Invalid request payload.", "INVALID_PAYLOAD", 400)

    question_user_id = None if getattr(user, "is_admin", False) else user.id
    questions = get_exam_questions_ordered(exam_id, user_id=question_user_id) or []
    if not questions:
        return error_response(
            "No questions for this exam.",
            "NO_QUESTIONS",
            400,
        )
    question_meta = {str(q.id): q.is_short_answer for q in questions}

    answers_v1, deprecated_input, error_code, error_message = (
        normalize_practice_answers_payload(data, question_meta)
    )
    if error_code:
        return error_response(error_message, error_code, 400)

    invalid_ids = [key for key in answers_v1.keys() if key not in question_meta]
    if invalid_ids:
        return error_response(
            "Question not in exam.",
            "QUESTION_NOT_IN_EXAM",
            400,
            details={"questionIds": invalid_ids},
        )

    summary, items = grade_exam_submission(
        exam_id, answers_v1, questions=questions, user_id=user.id
    )
    submitted_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    return jsonify(
        {
            "examId": exam.id,
            "submittedAt": submitted_at,
            "deprecatedInput": deprecated_input,
            "summary": summary,
            "items": items,
        }
    )


@api_practice_bp.route("/exam-set/submit", methods=["POST"])
def submit_exam_set_answers():
    user = current_user()
    raw_body = request.get_data(cache=True, as_text=True)
    data = request.get_json(silent=True)
    if data is None:
        if raw_body:
            return error_response("Invalid JSON.", "INVALID_JSON", 400)
        return error_response("Invalid request payload.", "INVALID_PAYLOAD", 400)

    exam_ids = _extract_exam_ids(data)
    if not exam_ids:
        return error_response(
            "At least one exam id is required.", "EXAM_IDS_REQUIRED", 400
        )

    exams, missing_ids = _resolve_scoped_exams(exam_ids, user)
    if missing_ids:
        return error_response(
            "One or more exams were not found.",
            "EXAM_NOT_FOUND",
            404,
            details={"examIds": missing_ids},
        )

    question_user_id = None if getattr(user, "is_admin", False) else user.id
    questions = get_exam_set_questions_ordered(exam_ids, user_id=question_user_id)
    if not questions:
        return error_response("No questions for selected exams.", "NO_QUESTIONS", 400)

    question_meta = {str(q.id): q.is_short_answer for q in questions}
    answers_v1, deprecated_input, error_code, error_message = (
        normalize_practice_answers_payload(data, question_meta)
    )
    if error_code:
        return error_response(error_message, error_code, 400)

    invalid_ids = [key for key in answers_v1.keys() if key not in question_meta]
    if invalid_ids:
        return error_response(
            "Question not in selected exams.",
            "QUESTION_NOT_IN_EXAMS",
            400,
            details={"questionIds": invalid_ids},
        )

    summary, items = grade_exam_set_submission(
        exam_ids,
        answers_v1,
        questions=questions,
        user_id=user.id,
        mode="exam_practice",
    )
    submitted_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    return jsonify(
        {
            "examIds": [exam.id for exam in exams],
            "title": _compose_exam_set_title(exams),
            "submittedAt": submitted_at,
            "deprecatedInput": deprecated_input,
            "summary": summary,
            "items": items,
        }
    )


@api_practice_bp.route("/sessions", methods=["POST"])
def create_session():
    user = current_user()
    raw_body = request.get_data(cache=True, as_text=True)
    data = request.get_json(silent=True)
    if data is None:
        if raw_body:
            return error_response("Invalid JSON.", "INVALID_JSON", 400)
        return error_response("Invalid request payload.", "INVALID_PAYLOAD", 400)

    mode = str(data.get("mode") or "practice")
    lecture_id = data.get("lectureId")
    exam_ids = _extract_exam_ids(data)

    question_user_id = None if getattr(user, "is_admin", False) else user.id

    if lecture_id is not None:
        try:
            lecture_id_value = int(lecture_id)
        except (TypeError, ValueError):
            return error_response("Invalid lecture id.", "INVALID_PAYLOAD", 400)

        lecture = get_scoped_by_id(Lecture, lecture_id_value, user, include_public=True)
        if lecture is None:
            return error_response("Lecture not found.", "LECTURE_NOT_FOUND", 404)

        all_questions = (
            get_lecture_questions_ordered(
                lecture_id_value,
                user_id=question_user_id,
            )
            or []
        )
        filtered_questions = all_questions
        if exam_ids:
            allowed = set(exam_ids)
            filtered_questions = [q for q in all_questions if q.exam_id in allowed]
        question_order = [q.id for q in filtered_questions]
        session = PracticeSession(
            lecture_id=lecture_id_value,
            user_id=user.id,
            lecture_ids_json=json.dumps(exam_ids, ensure_ascii=True),
            mode=mode,
            question_order=json.dumps(question_order, ensure_ascii=True),
            current_question_index=0,
            total_time_spent=0,
            submission_count=1,
        )
        db.session.add(session)
        db.session.commit()
        return jsonify(
            {
                "sessionId": session.id,
                "lectureId": lecture.id,
                "lectureTitle": lecture.title,
                "mode": session.mode,
                "questionOrder": question_order,
                "totalQuestions": len(question_order),
                "examIds": exam_ids,
            }
        )

    if exam_ids:
        exams, missing_ids = _resolve_scoped_exams(exam_ids, user)
        if missing_ids:
            return error_response(
                "One or more exams were not found.",
                "EXAM_NOT_FOUND",
                404,
                details={"examIds": missing_ids},
            )

        normalized_exam_ids = [exam.id for exam in exams]
        questions = get_exam_set_questions_ordered(
            normalized_exam_ids, user_id=question_user_id
        )
        question_order = [q.id for q in questions]
        session = PracticeSession(
            lecture_id=None,
            user_id=user.id,
            lecture_ids_json=json.dumps(normalized_exam_ids, ensure_ascii=True),
            mode="exam_practice" if mode == "practice" else mode,
            question_order=json.dumps(question_order, ensure_ascii=True),
            current_question_index=0,
            total_time_spent=0,
            submission_count=1,
        )
        db.session.add(session)
        db.session.commit()
        return jsonify(
            {
                "sessionId": session.id,
                "examIds": normalized_exam_ids,
                "examTitle": _compose_exam_set_title(exams),
                "mode": session.mode,
                "questionOrder": question_order,
                "totalQuestions": len(question_order),
            }
        )

    return error_response(
        "lectureId or examIds is required.",
        "INVALID_PAYLOAD",
        400,
    )


@api_practice_bp.route("/sessions/<int:session_id>/progress", methods=["PATCH"])
def save_session_progress(session_id):
    """Auto-save draft answers and current question index without grading."""
    user = current_user()
    session = get_scoped_by_id(PracticeSession, session_id, user)
    if session is None:
        return error_response("Session not found.", "SESSION_NOT_FOUND", 404)

    if session.finished_at is not None:
        return error_response(
            "Session already finished.", "SESSION_FINISHED", 400
        )

    raw_body = request.get_data(cache=True, as_text=True)
    data = request.get_json(silent=True)
    if data is None:
        if raw_body:
            return error_response("Invalid JSON.", "INVALID_JSON", 400)
        return error_response("Invalid request payload.", "INVALID_PAYLOAD", 400)

    with transaction():
        # Update current question index
        current_index = data.get("currentQuestionIndex")
        if current_index is not None:
            try:
                parsed_index = int(current_index)
                if parsed_index >= 0:
                    session.current_question_index = parsed_index
            except (TypeError, ValueError):
                pass

        # Update elapsed time
        elapsed = data.get("elapsedSeconds")
        if elapsed is not None:
            try:
                parsed_elapsed = int(elapsed)
                if parsed_elapsed >= 0:
                    session.total_time_spent = parsed_elapsed
            except (TypeError, ValueError):
                pass

        # Save draft answers (sync upsert without grading)
        answers_data = data.get("answers")
        if isinstance(answers_data, dict):
            valid_qids = _load_session_allowed_question_ids(session, user)
            existing_answer_rows = (
                PracticeAnswer.query.filter_by(session_id=session.id)
                .order_by(PracticeAnswer.id.asc())
                .all()
            )
            existing_answers = {}
            for answer in existing_answer_rows:
                key = str(answer.question_id)
                if key in existing_answers:
                    # Keep latest draft only.
                    db.session.delete(answer)
                    continue
                existing_answers[key] = answer
            next_answers = {}

            for question_id_str, payload in answers_data.items():
                if question_id_str not in valid_qids:
                    continue
                try:
                    qid = int(question_id_str)
                except (TypeError, ValueError):
                    continue
                next_answers[str(qid)] = payload

            # Remove answers that are no longer present in draft payload.
            for question_id_str, existing in existing_answers.items():
                if question_id_str not in next_answers:
                    db.session.delete(existing)

            for question_id_str, payload in next_answers.items():
                answer_json = json.dumps(payload, ensure_ascii=True)
                existing = existing_answers.get(question_id_str)
                if existing:
                    existing.answer_payload = answer_json
                    existing.is_correct = None  # draft: not graded
                    existing.answered_at = datetime.utcnow()
                    continue
                db.session.add(
                    PracticeAnswer(
                        session_id=session.id,
                        question_id=int(question_id_str),
                        answer_payload=answer_json,
                        is_correct=None,
                        answered_at=datetime.utcnow(),
                    )
                )

    return jsonify({
        "ok": True,
        "sessionId": session.id,
        "currentQuestionIndex": session.current_question_index,
    })


@api_practice_bp.route("/sessions/<int:session_id>/submit", methods=["POST"])
def submit_session_answers(session_id):
    user = current_user()
    session = get_scoped_by_id(PracticeSession, session_id, user)
    if session is None:
        return error_response("Session not found.", "SESSION_NOT_FOUND", 404)

    raw_body = request.get_data(cache=True, as_text=True)
    data = request.get_json(silent=True)
    if data is None:
        if raw_body:
            return error_response("Invalid JSON.", "INVALID_JSON", 400)
        return error_response("Invalid request payload.", "INVALID_PAYLOAD", 400)

    question_order = _load_session_question_order(session)
    ordered_questions = []
    if question_order:
        questions = (
            scope_query(Question.query, Question, user)
            .filter(Question.id.in_(question_order))
            .all()
        )
        question_map = {question.id: question for question in questions}
        ordered_questions = [
            question_map[qid] for qid in question_order if qid in question_map
        ]

    if not ordered_questions and session.lecture_id:
        question_user_id = None if getattr(user, "is_admin", False) else user.id
        ordered_questions = (
            get_lecture_questions_ordered(session.lecture_id, user_id=question_user_id)
            or []
        )

    if not ordered_questions:
        scoped_exam_ids = _load_session_scope_ids(session)
        if scoped_exam_ids:
            question_user_id = None if getattr(user, "is_admin", False) else user.id
            ordered_questions = get_exam_set_questions_ordered(
                scoped_exam_ids,
                user_id=question_user_id,
            )

    if not ordered_questions:
        return error_response("No questions for this session.", "NO_QUESTIONS", 400)

    question_meta = {str(q.id): q.is_short_answer for q in ordered_questions}
    answers_v1, deprecated_input, error_code, error_message = (
        normalize_practice_answers_payload(
            data,
            question_meta,
        )
    )
    if error_code:
        return error_response(error_message, error_code, 400)

    invalid_ids = [key for key in answers_v1.keys() if key not in question_meta]
    if invalid_ids:
        return error_response(
            "Question not in session.",
            "QUESTION_NOT_IN_SESSION",
            400,
            details={"questionIds": invalid_ids},
        )

    summary, items, _counts = evaluate_practice_answers(
        ordered_questions, answers_v1 or {}
    )

    PracticeAnswer.query.filter_by(session_id=session.id).delete()
    for item in items:
        if not item.get("isAnswered"):
            continue
        answer_payload = json.dumps(
            {"type": item.get("type"), "value": item.get("userAnswer")},
            ensure_ascii=True,
        )
        answer = PracticeAnswer(
            session_id=session.id,
            question_id=item.get("questionId"),
            answer_payload=answer_payload,
            is_correct=item.get("isCorrect"),
            answered_at=datetime.utcnow(),
        )
        db.session.add(answer)

    session.finished_at = datetime.utcnow()
    db.session.commit()

    scoped_exam_ids = _load_session_scope_ids(session)
    scoped_exams, _missing_exam_ids = _resolve_scoped_exams(scoped_exam_ids, user)
    submitted_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    return jsonify(
        {
            "sessionId": session.id,
            "lectureId": session.lecture_id,
            "examIds": [exam.id for exam in scoped_exams],
            "examTitle": _compose_exam_set_title(scoped_exams),
            "submittedAt": submitted_at,
            "deprecatedInput": deprecated_input,
            "summary": summary,
            "items": items,
        }
    )


@api_practice_bp.route("/sessions")
def list_sessions():
    user = current_user()
    lecture_id = request.args.get("lectureId")
    query = scope_query(PracticeSession.query, PracticeSession, user).order_by(
        PracticeSession.created_at.desc()
    )
    if lecture_id:
        if not lecture_id.isdigit():
            return error_response("Invalid lecture id.", "INVALID_PAYLOAD", 400)
        query = query.filter_by(lecture_id=int(lecture_id))

    sessions_payload = []
    for session in query.all():
        answers = session.answers
        answered_count = answers.count()
        correct_count = answers.filter_by(is_correct=True).count()
        question_order = _load_session_question_order(session)
        scoped_exam_ids = _load_session_scope_ids(session)
        scoped_exams, _missing_exam_ids = _resolve_scoped_exams(scoped_exam_ids, user)
        session_title = (
            session.lecture.title
            if session.lecture
            else _compose_exam_set_title(scoped_exams)
        )
        if question_order:
            total_questions = len(question_order)
        elif session.lecture:
            total_questions = (
                scope_query(Question.query, Question, user)
                .filter(Question.lecture_id == session.lecture_id)
                .count()
            )
        else:
            total_questions = answered_count

        sessions_payload.append(
            {
                "sessionId": session.id,
                "lectureId": session.lecture_id,
                "lectureTitle": session_title,
                "mode": session.mode,
                "createdAt": _format_datetime(session.created_at),
                "finishedAt": _format_datetime(session.finished_at),
                "totalQuestions": total_questions,
                "answeredCount": answered_count,
                "correctCount": correct_count,
                "examIds": [exam.id for exam in scoped_exams],
                "examTitle": _compose_exam_set_title(scoped_exams),
            }
        )

    return jsonify({"sessions": sessions_payload})


@api_practice_bp.route("/sessions/<int:session_id>")
def session_detail(session_id):
    user = current_user()
    session = get_scoped_by_id(PracticeSession, session_id, user)
    if session is None:
        return error_response("Session not found.", "SESSION_NOT_FOUND", 404)

    answers = session.answers.all()
    answer_map = {answer.question_id: answer for answer in answers}
    question_order = _load_session_question_order(session)
    scoped_exam_ids = _load_session_scope_ids(session)
    scoped_exams, _missing_exam_ids = _resolve_scoped_exams(scoped_exam_ids, user)

    if question_order:
        questions = (
            scope_query(Question.query, Question, user)
            .filter(Question.id.in_(question_order))
            .all()
        )
        question_map = {question.id: question for question in questions}
        ordered_questions = [
            question_map[qid] for qid in question_order if qid in question_map
        ]
    elif session.lecture_id:
        question_user_id = None if getattr(user, "is_admin", False) else user.id
        ordered_questions = (
            get_lecture_questions_ordered(session.lecture_id, user_id=question_user_id)
            or []
        )
    else:
        ordered_questions = [answer.question for answer in answers if answer.question]

    items = []
    for question in ordered_questions:
        answer = answer_map.get(question.id)
        payload = _parse_answer_payload(answer.answer_payload) if answer else None
        is_answered = answer is not None
        is_correct = answer.is_correct if answer is not None else None
        result = "unanswered"
        if answer is not None:
            result = "pending"
            if answer.is_correct is True:
                result = "correct"
            elif answer.is_correct is False:
                result = "wrong"

        items.append(
            {
                "questionId": question.id,
                "questionNumber": question.question_number,
                "isAnswered": is_answered,
                "isCorrect": is_correct,
                "answer": payload,
                "result": result,
            }
        )

    answers_query = session.answers
    answered_count = answers_query.count()
    correct_count = answers_query.filter_by(is_correct=True).count()
    if question_order:
        total_questions = len(question_order)
    elif ordered_questions:
        total_questions = len(ordered_questions)
    else:
        total_questions = answered_count

    return jsonify(
        {
            "sessionId": session.id,
            "lectureId": session.lecture_id,
            "lectureTitle": session.lecture.title if session.lecture else None,
            "examIds": [exam.id for exam in scoped_exams],
            "examTitle": _compose_exam_set_title(scoped_exams),
            "mode": session.mode,
            "createdAt": _format_datetime(session.created_at),
            "finishedAt": _format_datetime(session.finished_at),
            "totalQuestions": total_questions,
            "answeredCount": answered_count,
            "correctCount": correct_count,
            "questionOrder": question_order,
            "currentQuestionIndex": session.current_question_index or 0,
            "items": items,
        }
    )


@api_practice_bp.route("/lecture/<int:lecture_id>/result")
def lecture_result(lecture_id):
    user = current_user()
    lecture = get_scoped_by_id(Lecture, lecture_id, user, include_public=True)
    if lecture is None:
        return error_response("Lecture not found.", "LECTURE_NOT_FOUND", 404)

    include_answer = request.args.get("includeAnswer", "false").lower() == "true"
    limit, offset, error = _parse_pagination_args()
    if error:
        message, code = error
        return error_response(message, code, 400)

    exam_ids, filter_active = parse_exam_filter_args(request.args)
    query = scope_query(Question.query, Question, user).filter_by(lecture_id=lecture_id)
    if filter_active:
        if not exam_ids:
            response_payload = {
                "lectureId": lecture.id,
                "title": lecture.title,
                "total": 0,
                "offset": offset,
                "questions": [],
            }
            if limit is not None:
                response_payload["limit"] = limit
            return jsonify(response_payload)
        query = query.filter(Question.exam_id.in_(exam_ids))
    query = query.order_by(Question.question_number)
    total = query.count()
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    questions = query.all()
    question_ids = [question.id for question in questions]
    choices_by_question = _load_choices_for_questions(question_ids)
    questions_payload = [
        _build_question_payload(
            question,
            choices_by_question,
            include_answer=include_answer,
        )
        for question in questions
    ]

    response_payload = {
        "lectureId": lecture.id,
        "title": lecture.title,
        "total": total,
        "offset": offset,
        "questions": questions_payload,
    }
    if limit is not None:
        response_payload["limit"] = limit

    return jsonify(response_payload)


@api_practice_bp.route("/exam/<int:exam_id>/result")
def exam_result(exam_id):
    user = current_user()
    exam = get_scoped_by_id(PreviousExam, exam_id, user)
    if exam is None:
        return error_response("Exam not found.", "EXAM_NOT_FOUND", 404)

    include_answer = request.args.get("includeAnswer", "false").lower() == "true"
    limit, offset, error = _parse_pagination_args()
    if error:
        message, code = error
        return error_response(message, code, 400)

    query = scope_query(Question.query, Question, user).filter_by(exam_id=exam_id)
    query = query.order_by(Question.question_number)
    total = query.count()
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    questions = query.all()
    question_ids = [question.id for question in questions]
    choices_by_question = _load_choices_for_questions(question_ids)
    questions_payload = [
        _build_question_payload(
            question,
            choices_by_question,
            include_answer=include_answer,
        )
        for question in questions
    ]

    response_payload = {
        "examId": exam.id,
        "title": exam.title,
        "total": total,
        "offset": offset,
        "questions": questions_payload,
    }
    if limit is not None:
        response_payload["limit"] = limit

    return jsonify(response_payload)


@api_practice_bp.route("/exam-set/result")
def exam_set_result():
    user = current_user()
    exam_ids = _extract_exam_ids()
    if not exam_ids:
        return error_response(
            "At least one exam id is required.", "EXAM_IDS_REQUIRED", 400
        )

    exams, missing_ids = _resolve_scoped_exams(exam_ids, user)
    if missing_ids:
        return error_response(
            "One or more exams were not found.",
            "EXAM_NOT_FOUND",
            404,
            details={"examIds": missing_ids},
        )

    include_answer = request.args.get("includeAnswer", "false").lower() == "true"
    limit, offset, error = _parse_pagination_args()
    if error:
        message, code = error
        return error_response(message, code, 400)

    question_user_id = None if getattr(user, "is_admin", False) else user.id
    ordered_questions = get_exam_set_questions_ordered(
        exam_ids, user_id=question_user_id
    )
    total = len(ordered_questions)
    start = int(offset or 0)
    end = None
    if limit is not None:
        end = start + int(limit)
    questions = ordered_questions[start:end]

    question_ids = [question.id for question in questions]
    choices_by_question = _load_choices_for_questions(question_ids)
    questions_payload = [
        _build_question_payload(
            question,
            choices_by_question,
            include_answer=include_answer,
        )
        for question in questions
    ]

    response_payload = {
        "examIds": [exam.id for exam in exams],
        "title": _compose_exam_set_title(exams),
        "total": total,
        "offset": offset,
        "questions": questions_payload,
    }
    if limit is not None:
        response_payload["limit"] = limit
    return jsonify(response_payload)
