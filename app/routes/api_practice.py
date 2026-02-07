import json
import os
from datetime import datetime

from flask import Blueprint, jsonify, request, current_app, url_for
from sqlalchemy import func

from app.models import Block, Lecture, Question, Choice, PracticeSession, PreviousExam
from app.services.practice_service import (
    build_question_groups,
    get_exam_questions_ordered,
    get_lecture_questions_ordered,
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
from app.services.user_scope import (
    attach_current_user,
    current_user,
    get_scoped_by_id,
    scope_model,
    scope_query,
)
from app.services.block_sort import block_ordering

api_practice_bp = Blueprint('api_practice', __name__)


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
    payload = {'ok': False, 'code': code, 'message': message}
    if details is not None:
        payload['details'] = details
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
    return value.replace(microsecond=0).isoformat() + 'Z'


def _parse_pagination_args():
    limit_param = request.args.get('limit')
    offset_param = request.args.get('offset')
    limit = None
    offset = 0

    if offset_param is not None:
        if not offset_param.isdigit():
            return None, None, ('Invalid offset.', 'INVALID_PAYLOAD')
        offset = int(offset_param)
        if offset < 0:
            return None, None, ('Invalid offset.', 'INVALID_PAYLOAD')

    if limit_param is not None:
        if not limit_param.isdigit():
            return None, None, ('Invalid limit.', 'INVALID_PAYLOAD')
        limit = int(limit_param)
        if limit <= 0:
            return None, None, ('Invalid limit.', 'INVALID_PAYLOAD')

    return limit, offset, None


def _load_choices_for_questions(question_ids):
    if not question_ids:
        return {}
    choices = Choice.query.filter(Choice.question_id.in_(question_ids)).order_by(
        Choice.question_id, Choice.choice_number
    ).all()
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


@api_practice_bp.route('/lectures')
def list_lectures():
    user = current_user()
    blocks = scope_model(Block, user, include_public=True).order_by(*block_ordering()).all()
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
                'lectureId': lecture.id,
                'title': lecture.title,
                'order': lecture.order,
                'questionCount': question_counts.get(lecture.id, 0),
            }
            for lecture in block_lectures
        ]
        blocks_payload.append(
            {
                'blockId': block.id,
                'title': block.name,
                'lectures': lectures_payload,
            }
        )

    return jsonify({'blocks': blocks_payload})


@api_practice_bp.route('/lecture/<int:lecture_id>')
def lecture_questions(lecture_id):
    user = current_user()
    lecture = get_scoped_by_id(Lecture, lecture_id, user, include_public=True)
    if lecture is None:
        return error_response('Lecture not found.', 'LECTURE_NOT_FOUND', 404)

    exam_ids, filter_active = parse_exam_filter_args(request.args)
    question_user_id = None if getattr(user, "is_admin", False) else user.id
    all_questions = get_lecture_questions_ordered(
        lecture_id, user_id=question_user_id
    ) or []
    exam_options = build_exam_options(all_questions)
    questions = apply_exam_filter(all_questions, exam_ids, filter_active)
    groups = build_question_groups(questions)
    question_meta = groups['question_meta']
    question_map = {question.id: question for question in questions}
    selected_exam_ids = exam_ids if filter_active else [option['id'] for option in exam_options]

    questions_payload = []
    for meta in question_meta:
        question = question_map.get(meta['id'])
        exam = question.exam if question else None
        questions_payload.append(
            {
                'questionId': meta['id'],
                'originalSeq': meta['original_seq'],
                'typeSeq': meta['type_seq'],
                'type': meta['type'],
                'isShortAnswer': meta['is_short_answer'],
                'isMultipleResponse': meta['is_multiple_response'],
                'examId': question.exam_id if question else None,
                'examTitle': exam.title if exam else None,
            }
        )
    multiple_response_count = sum(
        1 for meta in question_meta if meta.get('is_multiple_response')
    )

    return jsonify(
        {
            'lectureId': lecture.id,
            'title': lecture.title,
            'questions': questions_payload,
            'totalCount': len(question_meta),
            'objectiveCount': len(groups['objective_questions']),
            'subjectiveCount': len(groups['subjective_questions']),
            'multipleResponseCount': multiple_response_count,
            'examOptions': exam_options,
            'selectedExamIds': selected_exam_ids,
            'filterActive': filter_active,
        }
    )


@api_practice_bp.route('/lecture/<int:lecture_id>/question/<int:question_id>')
def lecture_question(lecture_id, question_id):
    user = current_user()
    lecture = get_scoped_by_id(Lecture, lecture_id, user, include_public=True)
    if lecture is None:
        return error_response('Lecture not found.', 'LECTURE_NOT_FOUND', 404)

    question = (
        scope_query(Question.query, Question, user)
        .filter_by(id=question_id, lecture_id=lecture_id)
        .first()
    )
    if question is None:
        return error_response('Question not found in lecture.', 'QUESTION_NOT_IN_LECTURE', 404)

    choices = question.choices.order_by(Choice.choice_number).all()
    choices_payload = [
        {
            'number': choice.choice_number,
            'content': choice.content,
            'imageUrl': _build_upload_url(choice.image_path),
        }
        for choice in choices
    ]

    return jsonify(
        {
            'questionId': question.id,
            'stem': question.content or '',
            'choices': choices_payload,
            'isShortAnswer': question.is_short_answer,
            'isMultipleResponse': question.is_multiple_response,
            'hasExplanation': bool(question.explanation),
            'imageUrl': _build_upload_url(question.image_path),
        }
    )


@api_practice_bp.route('/lecture/<int:lecture_id>/questions')
def lecture_question_list(lecture_id):
    user = current_user()
    lecture = get_scoped_by_id(Lecture, lecture_id, user, include_public=True)
    if lecture is None:
        return error_response('Lecture not found.', 'LECTURE_NOT_FOUND', 404)

    limit, offset, error = _parse_pagination_args()
    if error:
        message, code = error
        return error_response(message, code, 400)

    exam_ids, filter_active = parse_exam_filter_args(request.args)
    query = scope_query(Question.query, Question, user).filter_by(
        lecture_id=lecture_id
    )
    if filter_active:
        if not exam_ids:
            response_payload = {
                'lectureId': lecture.id,
                'title': lecture.title,
                'total': 0,
                'offset': offset,
                'questions': [],
            }
            if limit is not None:
                response_payload['limit'] = limit
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

    questions_payload = []
    for question in questions:
        choices = choices_by_question.get(question.id, [])
        questions_payload.append(
            {
                'questionId': question.id,
                'stem': question.content or '',
                'choices': [
                    {
                        'number': choice.choice_number,
                        'content': choice.content,
                        'imageUrl': _build_upload_url(choice.image_path),
                    }
                    for choice in choices
                ],
                'isShortAnswer': question.is_short_answer,
                'isMultipleResponse': question.is_multiple_response,
                'examId': question.exam_id,
                'examTitle': question.exam.title if question.exam else None,
                'imageUrl': _build_upload_url(question.image_path),
            }
        )

    response_payload = {
        'lectureId': lecture.id,
        'title': lecture.title,
        'total': total,
        'offset': offset,
        'questions': questions_payload,
    }
    if limit is not None:
        response_payload['limit'] = limit

    return jsonify(response_payload)


@api_practice_bp.route('/exam/<int:exam_id>/questions')
def exam_question_list(exam_id):
    user = current_user()
    exam = get_scoped_by_id(PreviousExam, exam_id, user)
    if exam is None:
        return error_response('Exam not found.', 'EXAM_NOT_FOUND', 404)

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

    questions_payload = []
    for question in questions:
        choices = choices_by_question.get(question.id, [])
        questions_payload.append(
            {
                'questionId': question.id,
                'stem': question.content or '',
                'choices': [
                    {
                        'number': choice.choice_number,
                        'content': choice.content,
                        'imageUrl': _build_upload_url(choice.image_path),
                    }
                    for choice in choices
                ],
                'isShortAnswer': question.is_short_answer,
                'isMultipleResponse': question.is_multiple_response,
                'examId': question.exam_id,
                'examTitle': question.exam.title if question.exam else None,
                'imageUrl': _build_upload_url(question.image_path),
            }
        )

    response_payload = {
        'examId': exam.id,
        'title': exam.title,
        'total': total,
        'offset': offset,
        'questions': questions_payload,
    }
    if limit is not None:
        response_payload['limit'] = limit

    return jsonify(response_payload)


@api_practice_bp.route('/lecture/<int:lecture_id>/submit', methods=['POST'])
def submit_answers(lecture_id):
    user = current_user()
    lecture = get_scoped_by_id(Lecture, lecture_id, user, include_public=True)
    if lecture is None:
        return error_response('Lecture not found.', 'LECTURE_NOT_FOUND', 404)

    raw_body = request.get_data(cache=False, as_text=True)
    data = request.get_json(silent=True)
    if data is None:
        if raw_body:
            return error_response('Invalid JSON.', 'INVALID_JSON', 400)
        return error_response('Invalid request payload.', 'INVALID_PAYLOAD', 400)

    exam_ids, filter_active = parse_exam_filter_args(request.args)
    question_user_id = None if getattr(user, "is_admin", False) else user.id
    all_questions = get_lecture_questions_ordered(
        lecture_id, user_id=question_user_id
    ) or []
    questions = apply_exam_filter(all_questions, exam_ids, filter_active)
    if filter_active and not questions:
        return error_response(
            'No questions for the selected exams.',
            'NO_QUESTIONS',
            400,
        )
    question_meta = {str(q.id): q.is_short_answer for q in questions}

    answers_v1, deprecated_input, error_code, error_message = normalize_practice_answers_payload(
        data, question_meta
    )
    if error_code:
        return error_response(error_message, error_code, 400)

    invalid_ids = [
        key for key in answers_v1.keys() if key not in question_meta
    ]
    if invalid_ids:
        return error_response(
            'Question not in lecture.',
            'QUESTION_NOT_IN_LECTURE',
            400,
            details={'questionIds': invalid_ids},
        )

    summary, items = grade_practice_submission(
        lecture_id, answers_v1, user_id=user.id
    )
    submitted_at = datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'

    return jsonify(
        {
            'lectureId': lecture.id,
            'submittedAt': submitted_at,
            'deprecatedInput': deprecated_input,
            'summary': summary,
            'items': items,
        }
    )


@api_practice_bp.route('/exam/<int:exam_id>/submit', methods=['POST'])
def submit_exam_answers(exam_id):
    user = current_user()
    exam = get_scoped_by_id(PreviousExam, exam_id, user)
    if exam is None:
        return error_response('Exam not found.', 'EXAM_NOT_FOUND', 404)

    raw_body = request.get_data(cache=False, as_text=True)
    data = request.get_json(silent=True)
    if data is None:
        if raw_body:
            return error_response('Invalid JSON.', 'INVALID_JSON', 400)
        return error_response('Invalid request payload.', 'INVALID_PAYLOAD', 400)

    question_user_id = None if getattr(user, "is_admin", False) else user.id
    questions = get_exam_questions_ordered(exam_id, user_id=question_user_id) or []
    if not questions:
        return error_response(
            'No questions for this exam.',
            'NO_QUESTIONS',
            400,
        )
    question_meta = {str(q.id): q.is_short_answer for q in questions}

    answers_v1, deprecated_input, error_code, error_message = normalize_practice_answers_payload(
        data, question_meta
    )
    if error_code:
        return error_response(error_message, error_code, 400)

    invalid_ids = [key for key in answers_v1.keys() if key not in question_meta]
    if invalid_ids:
        return error_response(
            'Question not in exam.',
            'QUESTION_NOT_IN_EXAM',
            400,
            details={'questionIds': invalid_ids},
        )

    summary, items = grade_exam_submission(
        exam_id, answers_v1, questions=questions, user_id=user.id
    )
    submitted_at = datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'

    return jsonify(
        {
            'examId': exam.id,
            'submittedAt': submitted_at,
            'deprecatedInput': deprecated_input,
            'summary': summary,
            'items': items,
        }
    )


@api_practice_bp.route('/sessions')
def list_sessions():
    user = current_user()
    lecture_id = request.args.get('lectureId')
    query = scope_query(PracticeSession.query, PracticeSession, user).order_by(
        PracticeSession.created_at.desc()
    )
    if lecture_id:
        if not lecture_id.isdigit():
            return error_response('Invalid lecture id.', 'INVALID_PAYLOAD', 400)
        query = query.filter_by(lecture_id=int(lecture_id))

    sessions_payload = []
    for session in query.all():
        answers = session.answers
        answered_count = answers.count()
        correct_count = answers.filter_by(is_correct=True).count()
        question_order = _load_session_question_order(session)
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
                'sessionId': session.id,
                'lectureId': session.lecture_id,
                'lectureTitle': session.lecture.title if session.lecture else None,
                'mode': session.mode,
                'createdAt': _format_datetime(session.created_at),
                'finishedAt': _format_datetime(session.finished_at),
                'totalQuestions': total_questions,
                'answeredCount': answered_count,
                'correctCount': correct_count,
            }
        )

    return jsonify({'sessions': sessions_payload})


@api_practice_bp.route('/sessions/<int:session_id>')
def session_detail(session_id):
    user = current_user()
    session = get_scoped_by_id(PracticeSession, session_id, user)
    if session is None:
        return error_response('Session not found.', 'SESSION_NOT_FOUND', 404)

    answers = session.answers.all()
    answer_map = {answer.question_id: answer for answer in answers}
    question_order = _load_session_question_order(session)

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
            get_lecture_questions_ordered(
                session.lecture_id, user_id=question_user_id
            )
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
        result = 'unanswered'
        if answer is not None:
            result = 'pending'
            if answer.is_correct is True:
                result = 'correct'
            elif answer.is_correct is False:
                result = 'wrong'

        items.append(
            {
                'questionId': question.id,
                'questionNumber': question.question_number,
                'isAnswered': is_answered,
                'isCorrect': is_correct,
                'answer': payload,
                'result': result,
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
            'sessionId': session.id,
            'lectureId': session.lecture_id,
            'lectureTitle': session.lecture.title if session.lecture else None,
            'mode': session.mode,
            'createdAt': _format_datetime(session.created_at),
            'finishedAt': _format_datetime(session.finished_at),
            'totalQuestions': total_questions,
            'answeredCount': answered_count,
            'correctCount': correct_count,
            'questionOrder': question_order,
            'items': items,
        }
    )


@api_practice_bp.route('/lecture/<int:lecture_id>/result')
def lecture_result(lecture_id):
    user = current_user()
    lecture = get_scoped_by_id(Lecture, lecture_id, user, include_public=True)
    if lecture is None:
        return error_response('Lecture not found.', 'LECTURE_NOT_FOUND', 404)

    include_answer = request.args.get('includeAnswer', 'false').lower() == 'true'
    limit, offset, error = _parse_pagination_args()
    if error:
        message, code = error
        return error_response(message, code, 400)

    exam_ids, filter_active = parse_exam_filter_args(request.args)
    query = scope_query(Question.query, Question, user).filter_by(lecture_id=lecture_id)
    if filter_active:
        if not exam_ids:
            response_payload = {
                'lectureId': lecture.id,
                'title': lecture.title,
                'total': 0,
                'offset': offset,
                'questions': [],
            }
            if limit is not None:
                response_payload['limit'] = limit
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
    questions_payload = []
    for question in questions:
        choices = choices_by_question.get(question.id, [])
        question_payload = {
            'questionId': question.id,
            'stem': question.content or '',
            'choices': [
                {
                    'number': choice.choice_number,
                    'content': choice.content,
                    'imageUrl': _build_upload_url(choice.image_path),
                }
                for choice in choices
            ],
            'explanation': question.explanation,
            'isShortAnswer': question.is_short_answer,
            'isMultipleResponse': question.is_multiple_response,
            'imageUrl': _build_upload_url(question.image_path),
        }
        if include_answer:
            if question.is_short_answer:
                question_payload['correctAnswerText'] = question.correct_answer_text
            else:
                question_payload['correctChoiceNumbers'] = [
                    choice.choice_number for choice in choices if choice.is_correct
                ]
        questions_payload.append(question_payload)

    response_payload = {
        'lectureId': lecture.id,
        'title': lecture.title,
        'total': total,
        'offset': offset,
        'questions': questions_payload,
    }
    if limit is not None:
        response_payload['limit'] = limit

    return jsonify(response_payload)


@api_practice_bp.route('/exam/<int:exam_id>/result')
def exam_result(exam_id):
    user = current_user()
    exam = get_scoped_by_id(PreviousExam, exam_id, user)
    if exam is None:
        return error_response('Exam not found.', 'EXAM_NOT_FOUND', 404)

    include_answer = request.args.get('includeAnswer', 'false').lower() == 'true'
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
    questions_payload = []
    for question in questions:
        choices = choices_by_question.get(question.id, [])
        question_payload = {
            'questionId': question.id,
            'stem': question.content or '',
            'choices': [
                {
                    'number': choice.choice_number,
                    'content': choice.content,
                    'imageUrl': _build_upload_url(choice.image_path),
                }
                for choice in choices
            ],
            'explanation': question.explanation,
            'isShortAnswer': question.is_short_answer,
            'isMultipleResponse': question.is_multiple_response,
            'imageUrl': _build_upload_url(question.image_path),
        }
        if include_answer:
            if question.is_short_answer:
                question_payload['correctAnswerText'] = question.correct_answer_text
            else:
                question_payload['correctChoiceNumbers'] = [
                    choice.choice_number for choice in choices if choice.is_correct
                ]
        questions_payload.append(question_payload)

    response_payload = {
        'examId': exam.id,
        'title': exam.title,
        'total': total,
        'offset': offset,
        'questions': questions_payload,
    }
    if limit is not None:
        response_payload['limit'] = limit

    return jsonify(response_payload)
