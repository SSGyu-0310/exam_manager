"""시험 관련 Blueprint - 기출 시험 및 문제 조회"""
import time
import logging
import os
from urllib.parse import urlencode
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    current_app,
    abort,
)
from app import db
from app.models import PreviousExam, Question, Block, Lecture
from app.services.db_guard import guard_write_request
from app.services.user_scope import (
    attach_current_user,
    current_user,
    get_scoped_by_id,
    scope_model,
    scope_query,
)
from app.services.block_sort import block_ordering

logger = logging.getLogger(__name__)

exam_bp = Blueprint('exam', __name__)

VALID_STATUS_FILTERS = {'unclassified', 'classified', 'all'}


def _parse_question_filters():
    status = request.args.get('status', 'unclassified')
    if status not in VALID_STATUS_FILTERS:
        status = 'unclassified'
    exam_id_raw = (request.args.get('exam_id') or '').strip()
    exam_id = None
    if exam_id_raw and exam_id_raw != 'all':
        try:
            exam_id = int(exam_id_raw)
        except ValueError:
            exam_id = None
    search_query = (request.args.get('query') or '').strip()
    return status, exam_id, search_query


def _apply_question_filters(query, status, exam_id, search_query):
    if status == 'unclassified':
        query = query.filter_by(is_classified=False)
    elif status == 'classified':
        query = query.filter_by(is_classified=True)
    if exam_id is not None:
        query = query.filter(Question.exam_id == exam_id)
    if search_query:
        query = query.filter(Question.content.ilike(f"%{search_query}%"))
    return query


@exam_bp.before_request
def guard_read_only():
    blocked = guard_write_request()
    if blocked is not None:
        return blocked
    return None


@exam_bp.before_request
def attach_user():
    return attach_current_user(require=True)


def _require_user_json():
    error = attach_current_user(require=True)
    if error is not None:
        return None, error
    user = current_user()
    if user is None:
        return None, (jsonify({"success": False, "error": "Authentication required."}), 401)
    return user, None


@exam_bp.route('/')
def list_exams():
    """기출 시험 목록 조회"""
    user = current_user()
    exams = scope_model(PreviousExam, user).order_by(PreviousExam.exam_date.desc()).all()
    return render_template('exam/list.html', exams=exams)


@exam_bp.route('/<int:exam_id>')
def view_exam(exam_id):
    """기출 시험 상세 조회"""
    user = current_user()
    exam = get_scoped_by_id(PreviousExam, exam_id, user)
    if not exam:
        abort(404)
    questions = (
        scope_query(Question.query, Question, user)
        .filter(Question.exam_id == exam.id)
        .order_by(Question.question_number)
        .all()
    )
    
    # 분류 현황 계산
    classified_count = exam.classified_count
    total_count = exam.question_count
    
    return render_template('exam/detail.html', 
                         exam=exam, 
                         questions=questions,
                         classified_count=classified_count,
                         total_count=total_count)


@exam_bp.route('/<int:exam_id>/question/<int:question_number>')
def view_question(exam_id, question_number):
    """문제 상세 조회"""
    user = current_user()
    exam = get_scoped_by_id(PreviousExam, exam_id, user)
    if not exam:
        abort(404)
    question = (
        scope_query(Question.query, Question, user)
        .filter(
            Question.exam_id == exam_id,
            Question.question_number == question_number,
        )
        .first()
    )
    if not question:
        abort(404)

    prev_question = (
        scope_query(Question.query, Question, user)
        .filter(
            Question.exam_id == exam_id,
            Question.question_number < question_number,
        )
        .order_by(Question.question_number.desc())
        .first()
    )
    next_question = (
        scope_query(Question.query, Question, user)
        .filter(
            Question.exam_id == exam_id,
            Question.question_number > question_number,
        )
        .order_by(Question.question_number.asc())
        .first()
    )
    prev_url = (
        url_for("exam.view_question", exam_id=exam_id, question_number=prev_question.question_number)
        if prev_question
        else None
    )
    next_url = (
        url_for("exam.view_question", exam_id=exam_id, question_number=next_question.question_number)
        if next_question
        else None
    )

    original_image_url = None
    upload_folder = current_app.config.get("UPLOAD_FOLDER") or os.path.join(
        current_app.static_folder, "uploads"
    )
    from app.services.pdf_cropper import find_question_crop_image, to_static_relative

    crop_path = find_question_crop_image(
        exam.id, question.question_number, upload_folder=upload_folder
    )
    if crop_path:
        relative_path = to_static_relative(
            crop_path, static_root=current_app.static_folder
        )
        if relative_path:
            original_image_url = url_for("static", filename=relative_path)

    # 분류 가능한 강의 목록
    blocks = scope_model(Block, user, include_public=True).order_by(*block_ordering()).all()

    return render_template(
        'exam/question.html',
        exam=exam,
        question=question,
        blocks=blocks,
        original_image_url=original_image_url,
        prev_url=prev_url,
        next_url=next_url,
    )


@exam_bp.route('/unclassified')
def unclassified_questions():
    """분류 대기소 페이지 - 필터/페이지네이션"""
    user = current_user()
    t_start = time.perf_counter()

    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = min(per_page, 100)  # Cap at 100

    status, exam_id, search_query = _parse_question_filters()

    # 문제 조회 (기본적으로 미분류 우선) - 페이지네이션
    t_db_start = time.perf_counter()
    query = scope_query(Question.query, Question, user)
    query = _apply_question_filters(query, status, exam_id, search_query)
    pagination = query.order_by(
        Question.is_classified,  # False(미분류)가 먼저
        Question.exam_id,
        Question.question_number
    ).paginate(page=page, per_page=per_page, error_out=False)
    questions = pagination.items
    t_db = time.perf_counter() - t_db_start

    # 블록 목록 (강의 포함)
    blocks = scope_model(Block, user, include_public=True).order_by(*block_ordering()).all()

    # 시험 목록 (필터용)
    exams = scope_model(PreviousExam, user).order_by(PreviousExam.created_at.desc()).all()

    # 미분류 문제 수
    unclassified_count = scope_query(Question.query, Question, user).filter_by(is_classified=False).count()

    filter_params = {'status': status}
    if exam_id is not None:
        filter_params['exam_id'] = exam_id
    if search_query:
        filter_params['query'] = search_query
    if request.args.get('per_page'):
        filter_params['per_page'] = per_page
    filter_query = f"&{urlencode(filter_params)}" if filter_params else ''

    t_render_start = time.perf_counter()
    result = render_template('exam/unclassified.html',
                         questions=questions,
                         pagination=pagination,
                         blocks=blocks,
                         exams=exams,
                         unclassified_count=unclassified_count,
                         selected_status=status,
                         selected_exam_id=exam_id,
                         search_query=search_query,
                         filter_query=filter_query,
                         filtered_total=pagination.total)
    t_render = time.perf_counter() - t_render_start

    t_total = time.perf_counter() - t_start
    logger.info(
        "PERF: unclassified total=%.0fms db=%.0fms render=%.0fms count=%d page=%d",
        t_total * 1000, t_db * 1000, t_render * 1000, len(questions), page
    )

    return result


@exam_bp.route('/questions/ids')
def list_question_ids():
    user, auth_error = _require_user_json()
    if auth_error is not None:
        return auth_error

    status, exam_id, search_query = _parse_question_filters()
    query = scope_query(Question.query, Question, user)
    query = _apply_question_filters(query, status, exam_id, search_query)
    ids = [row[0] for row in query.with_entities(Question.id).all()]
    return jsonify({'success': True, 'ids': ids, 'total': len(ids)})


@exam_bp.route('/question/<int:question_id>/classify', methods=['POST'])
def classify_question(question_id):
    """문제를 강의에 분류 (AJAX 지원)"""
    user, auth_error = _require_user_json()
    if auth_error is not None:
        return auth_error

    question = get_scoped_by_id(Question, question_id, user)
    if not question:
        return jsonify({'success': False, 'error': '문제를 찾을 수 없습니다.'}), 404
    lecture_id = request.form.get('lecture_id', type=int)

    # AJAX 요청 확인
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if lecture_id:
        lecture = get_scoped_by_id(Lecture, lecture_id, user, include_public=True)
        if lecture:
            question.classify(lecture_id)
            db.session.commit()

            if is_ajax:
                unclassified_count = (
                    scope_query(Question.query, Question, user)
                    .filter_by(is_classified=False)
                    .count()
                )
                return jsonify({
                    'success': True,
                    'lecture_name': f"{lecture.block.name} > {lecture.title}",
                    'lecture_id': lecture_id,
                    'unclassified_count': unclassified_count,
                })

            flash('문제가 분류되었습니다.', 'success')
        else:
            if is_ajax:
                return jsonify({'success': False, 'error': '강의를 찾을 수 없습니다.'})
            flash('강의를 찾을 수 없습니다.', 'error')
    else:
        if is_ajax:
            return jsonify({'success': False, 'error': '강의를 선택해주세요.'})
        flash('강의를 선택해주세요.', 'error')

    return redirect(url_for('exam.view_question',
                          exam_id=question.exam_id,
                          question_number=question.question_number))


@exam_bp.route('/question/<int:question_id>/unclassify', methods=['POST'])
def unclassify_question(question_id):
    """문제 분류 해제"""
    user, auth_error = _require_user_json()
    if auth_error is not None:
        return auth_error

    question = get_scoped_by_id(Question, question_id, user)
    if not question:
        return jsonify({'success': False, 'error': '문제를 찾을 수 없습니다.'}), 404
    question.unclassify()
    db.session.commit()
    
    # AJAX 요청 확인
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    
    flash('분류가 해제되었습니다.', 'info')
    return redirect(url_for('exam.view_question', 
                          exam_id=question.exam_id, 
                          question_number=question.question_number))


@exam_bp.route('/questions/bulk-classify', methods=['POST'])
def bulk_classify():
    """여러 문제를 한 번에 분류"""
    user, auth_error = _require_user_json()
    if auth_error is not None:
        return auth_error

    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': '데이터가 없습니다.'}), 400
    
    question_ids = data.get('question_ids', [])
    lecture_id = data.get('lecture_id')
    
    if not question_ids:
        return jsonify({'success': False, 'error': '선택된 문제가 없습니다.'}), 400
    
    if not lecture_id:
        return jsonify({'success': False, 'error': '강의를 선택해주세요.'}), 400

    lecture = get_scoped_by_id(Lecture, lecture_id, user, include_public=True)
    if not lecture:
        return jsonify({'success': False, 'error': '강의를 찾을 수 없습니다.'}), 404

    # 선택된 문제들 일괄 분류
    updated_count = (
        scope_query(Question.query, Question, user)
        .filter(Question.id.in_(question_ids))
        .update(
            {"lecture_id": lecture.id, "is_classified": True, "classification_status": "manual"},
            synchronize_session=False,
        )
    )

    db.session.commit()
    unclassified_count = (
        scope_query(Question.query, Question, user)
        .filter_by(is_classified=False)
        .count()
    )

    return jsonify({
        'success': True,
        'updated_count': updated_count,
        'lecture_name': f"{lecture.block.name} > {lecture.title}",
        'unclassified_count': unclassified_count,
    })

