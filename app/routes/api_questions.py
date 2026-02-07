"""JSON API for question evidence."""
from flask import Blueprint, jsonify, current_app, abort, request
from sqlalchemy.orm import selectinload

from app.models import Question, QuestionChunkMatch, Lecture
from app.services.user_scope import attach_current_user, current_user, get_scoped_by_id

api_questions_bp = Blueprint('api_questions', __name__, url_prefix='/api/questions')


@api_questions_bp.before_request
def restrict_to_local_admin():
    if not current_app.config.get('LOCAL_ADMIN_ONLY'):
        return None
    remote_addr = request.remote_addr or ''
    if remote_addr not in {'127.0.0.1', '::1'}:
        abort(404)
    return None


@api_questions_bp.before_request
def attach_user():
    return attach_current_user(require=True)


def ok(data=None, status=200):
    return jsonify({'ok': True, 'data': data}), status


@api_questions_bp.get('/<int:question_id>/evidence')
def get_question_evidence(question_id):
    user = current_user()
    question = get_scoped_by_id(Question, question_id, user)
    if not question:
        return jsonify({'ok': False, 'message': 'Question not found.'}), 404
    matches = (
        QuestionChunkMatch.query.filter_by(question_id=question.id)
        .options(
            selectinload(QuestionChunkMatch.lecture).selectinload(Lecture.block),
            selectinload(QuestionChunkMatch.material),
        )
        .order_by(QuestionChunkMatch.is_primary.desc(), QuestionChunkMatch.id)
        .all()
    )
    payload = []
    for match in matches:
        lecture = match.lecture
        material = match.material
        payload.append(
            {
                'id': match.id,
                'questionId': match.question_id,
                'lectureId': match.lecture_id,
                'lectureTitle': lecture.title if lecture else None,
                'blockId': lecture.block_id if lecture and lecture.block else None,
                'blockName': lecture.block.name if lecture and lecture.block else None,
                'chunkId': match.chunk_id,
                'materialId': match.material_id,
                'materialPath': material.file_path if material else None,
                'materialFilename': material.original_filename if material else None,
                'pageStart': match.page_start,
                'pageEnd': match.page_end,
                'snippet': match.snippet,
                'score': match.score,
                'source': match.source,
                'jobId': match.job_id,
                'isPrimary': bool(match.is_primary),
                'createdAt': match.created_at.isoformat() if match.created_at else None,
            }
        )

    return ok({'questionId': question.id, 'evidence': payload})
