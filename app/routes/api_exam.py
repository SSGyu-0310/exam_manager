"""JSON API for exam screens (unclassified queue)."""
from flask import Blueprint, request, jsonify, current_app, abort

from app.models import PreviousExam, Question, Block, Lecture

api_exam_bp = Blueprint('api_exam', __name__, url_prefix='/api/exam')


@api_exam_bp.before_request
def restrict_to_local_admin():
    if not current_app.config.get('LOCAL_ADMIN_ONLY'):
        return None
    remote_addr = request.remote_addr or ''
    if remote_addr not in {'127.0.0.1', '::1'}:
        abort(404)
    return None


def ok(data=None, status=200):
    return jsonify({'ok': True, 'data': data}), status


def _exam_payload(exam):
    return {
        'id': exam.id,
        'title': exam.title,
        'examDate': exam.exam_date.isoformat() if exam.exam_date else None,
        'questionCount': exam.question_count,
    }


def _lecture_payload(lecture):
    return {
        'id': lecture.id,
        'title': lecture.title,
    }


def _block_payload(block):
    return {
        'id': block.id,
        'name': block.name,
        'lectures': [_lecture_payload(lecture) for lecture in block.lectures.order_by(Lecture.order)],
    }


def _question_payload(question):
    content = question.content or ''
    snippet = content.replace('\n', ' ').strip()
    if len(snippet) > 160:
        snippet = snippet[:157] + '...'
    return {
        'id': question.id,
        'examId': question.exam_id,
        'examTitle': question.exam.title if question.exam else None,
        'questionNumber': question.question_number,
        'type': question.q_type,
        'lectureId': question.lecture_id,
        'lectureTitle': question.lecture.title if question.lecture else None,
        'blockId': question.lecture.block_id if question.lecture else None,
        'blockName': question.lecture.block.name if question.lecture else None,
        'isClassified': question.is_classified,
        'snippet': snippet,
        'hasImage': bool(question.image_path),
    }


@api_exam_bp.get('/unclassified')
def list_unclassified():
    status = request.args.get('status', 'unclassified')
    exam_id = request.args.get('examId')
    query = request.args.get('query', '').strip()

    try:
        limit = int(request.args.get('limit', 200))
        offset = int(request.args.get('offset', 0))
    except ValueError:
        limit = 200
        offset = 0

    q = Question.query
    if status != 'all':
        q = q.filter_by(is_classified=False)
    if exam_id:
        try:
            exam_id_value = int(exam_id)
            q = q.filter(Question.exam_id == exam_id_value)
        except ValueError:
            return jsonify(
                {'ok': False, 'code': 'INVALID_EXAM_ID', 'message': 'Invalid exam id.'}
            ), 400
    if query:
        q = q.filter(Question.content.contains(query))

    total = q.count()
    questions = (
        q.order_by(Question.is_classified, Question.exam_id, Question.question_number)
        .offset(offset)
        .limit(limit)
        .all()
    )

    blocks = Block.query.order_by(Block.order).all()
    exams = PreviousExam.query.order_by(PreviousExam.created_at.desc()).all()
    unclassified_count = Question.query.filter_by(is_classified=False).count()

    return ok(
        {
            'items': [_question_payload(question) for question in questions],
            'total': total,
            'offset': offset,
            'limit': limit,
            'unclassifiedCount': unclassified_count,
            'blocks': [_block_payload(block) for block in blocks],
            'exams': [_exam_payload(exam) for exam in exams],
        }
    )
