"""AI 분류 관련 API Blueprint"""
import json
import os
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from flask import Blueprint, request, render_template, current_app
from app import db
from app.models import Question, Block, PreviousExam, ClassificationJob, Lecture
from app.services.ai_classifier import (
    AsyncBatchProcessor,
    apply_classification_results,
    build_job_diagnostics,
    GENAI_AVAILABLE,
    parse_job_payload,
)
from app.services.classification_scope import (
    normalize_classification_scope,
    resolve_scope_lecture_ids,
)
from app.services.folder_scope import parse_bool, resolve_lecture_ids
from app.services.db_guard import guard_write_request
from app.services.user_scope import (
    attach_current_user,
    current_user,
    get_scoped_by_id,
    scope_model,
    scope_query,
)
from app.services.block_sort import block_ordering
from app.services.api_response import (
    success_response as _success_response,
    error_response as _error_response,
)
from config import get_config

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover - fallback for older runtimes
    ZoneInfo = None  # type: ignore[assignment]

# Google GenAI SDK (for text correction)
try:
    from google import genai
    from google.genai import types
except ImportError:
    pass

ai_bp = Blueprint('ai', __name__, url_prefix='/ai')
_KST_TZ = ZoneInfo("Asia/Seoul") if ZoneInfo else timezone(timedelta(hours=9))


def _json_success(payload: Optional[dict] = None, status: int = 200):
    body = payload or {}
    data = dict(body)
    data.pop("success", None)
    return _success_response(
        data=data or None,
        status=status,
        legacy={"success": True, **body},
    )


def _json_error(
    message: str,
    code: str = "BAD_REQUEST",
    status: int = 400,
    payload: Optional[dict] = None,
):
    body = payload or {}
    data = dict(body)
    data.pop("success", None)
    data.pop("error", None)
    return _error_response(
        message=message,
        code=code,
        status=status,
        data=data or None,
        legacy={"success": False, "error": message, **body},
    )


def _format_kst(dt: Optional[datetime], fmt: str = "%m/%d %H:%M") -> Optional[str]:
    if dt is None:
        return None
    aware = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    return aware.astimezone(_KST_TZ).strftime(fmt)


@ai_bp.before_request
def guard_read_only():
    if request.endpoint in {'ai.correct_text'}:
        return None
    blocked = guard_write_request()
    if blocked is not None:
        return blocked
    return None


@ai_bp.before_request
def attach_user():
    if request.endpoint in {'ai.correct_text'}:
        return None
    return attach_current_user(require=True)


def _build_request_signature(question_ids, idempotency_key=None, scope=None):
    payload = {'question_ids': question_ids}
    if idempotency_key:
        payload['idempotency_key'] = str(idempotency_key)
    if scope:
        payload['scope'] = scope
    raw = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _build_super_request_signature(
    exam_id,
    question_ids,
    idempotency_key=None,
    scope=None,
):
    payload = {
        'kind': 'super',
        'exam_id': int(exam_id),
        'question_ids': question_ids,
    }
    if idempotency_key:
        payload['idempotency_key'] = str(idempotency_key)
    if scope:
        payload['scope'] = scope
    raw = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _super_trusted_emails() -> set[str]:
    raw = os.environ.get("SUPER_CLASSIFY_TRUSTED_EMAILS", "hisukgyu@gmail.com")
    return {
        token.strip().lower()
        for token in raw.split(",")
        if token and token.strip()
    }


def _is_super_unrestricted_user(user) -> bool:
    if user is None:
        return False
    if getattr(user, "is_admin", False):
        return True
    if current_app.config.get("ENV_NAME") == "production":
        return False
    email = (getattr(user, "email", "") or "").strip().lower()
    if not email:
        return False
    return email in _super_trusted_emails()


def _find_recent_job(signature, max_age_hours=24):
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    jobs = ClassificationJob.query.filter(
        ClassificationJob.created_at >= cutoff
    ).order_by(ClassificationJob.created_at.desc()).all()
    for job in jobs:
        request_meta, _ = parse_job_payload(job.result_json)
        if request_meta.get('signature') == signature:
            return job
    return None


def _normalize_int_id_list(raw_values) -> list[int]:
    if not isinstance(raw_values, (list, tuple, set)):
        return []
    normalized: list[int] = []
    for raw in raw_values:
        try:
            normalized.append(int(raw))
        except (TypeError, ValueError):
            continue
    return sorted(set(normalized))


def _super_retry_missing_question_ids(job) -> list[int]:
    request_meta, results = parse_job_payload(job.result_json)
    requested_ids = _normalize_int_id_list(request_meta.get("question_ids") or [])
    if not requested_ids:
        return []

    seen_ids: set[int] = set()
    omitted_ids: set[int] = set()
    for result in results or []:
        if not isinstance(result, dict):
            continue
        raw_question_id = result.get("question_id")
        try:
            question_id = int(raw_question_id)
        except (TypeError, ValueError):
            continue
        seen_ids.add(question_id)
        if parse_bool(result.get("response_omitted"), False):
            omitted_ids.add(question_id)
        elif str(result.get("reason") or "").strip() == "모델 응답 누락으로 자동 no_match 처리":
            # Backward compatibility for jobs created before response_omitted flag.
            omitted_ids.add(question_id)

    missing_ids = set(requested_ids) - seen_ids
    retry_ids = sorted((missing_ids | omitted_ids) & set(requested_ids))
    return retry_ids


def _job_visible_to_user(job, user) -> bool:
    if user is None:
        return False
    request_meta, _ = parse_job_payload(job.result_json)
    if getattr(user, "is_admin", False):
        return True
    if request_meta.get("super_classify") and _is_super_unrestricted_user(user):
        return True
    question_ids = request_meta.get("question_ids") or []
    if not question_ids:
        return False
    allowed = (
        scope_query(Question.query, Question, user)
        .filter(Question.id.in_(question_ids))
        .count()
    )
    return allowed == len(set(question_ids))


@ai_bp.route('/classify/start', methods=['POST'])
def start_classification():
    """AI 분류 작업 시작"""
    user = current_user()
    if not GENAI_AVAILABLE:
        return _json_error(
            "google-genai 패키지가 설치되지 않았습니다.",
            code="GENAI_NOT_AVAILABLE",
            status=500,
        )
    
    data = request.get_json()
    if data is None:
        return _json_error("데이터가 없습니다.", code="INVALID_PAYLOAD", status=400)
    
    question_ids = data.get('question_ids') or data.get('questionIds') or []
    if not question_ids:
        return _json_error(
            "선택된 문제가 없습니다.", code="QUESTION_IDS_REQUIRED", status=400
        )
    
    # 유효한 문제 ID만 필터링
    valid_ids = [
        q.id
        for q in scope_query(Question.query, Question, user)
        .filter(Question.id.in_(question_ids))
        .all()
    ]
    
    if not valid_ids:
        return _json_error(
            "유효한 문제가 없습니다.", code="VALID_QUESTIONS_REQUIRED", status=400
        )

    valid_ids = sorted(set(valid_ids))
    idempotency_key = data.get('idempotency_key') or data.get('idempotencyKey')
    force = bool(data.get('force'))
    retry_failed = bool(data.get('retry') or data.get('retry_failed') or data.get('retryFailed'))

    scope = resolve_scope_lecture_ids(
        normalize_classification_scope(data.get('scope')),
        user=user,
        include_public=True,
    )

    signature = _build_request_signature(valid_ids, idempotency_key, scope or None)

    existing_job = None
    if not force:
        existing_job = _find_recent_job(signature)
        if existing_job and not _job_visible_to_user(existing_job, user):
            existing_job = None

    if existing_job and existing_job.status not in (
        ClassificationJob.STATUS_FAILED,
        ClassificationJob.STATUS_CANCELLED,
    ):
        return _json_success({
            'success': True,
            'job_id': existing_job.id,
            'total_count': existing_job.total_count,
            'status': existing_job.status,
            'reused': True,
            'request_signature': signature
        })
    if (
        existing_job
        and existing_job.status in (
            ClassificationJob.STATUS_FAILED,
            ClassificationJob.STATUS_CANCELLED,
        )
        and not retry_failed
    ):
        existing_job = None

    requested_at = datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
    request_meta = {
        'signature': signature,
        'question_ids': valid_ids,
        'requested_at': requested_at,
        'scope_user_id': user.id,
    }
    if idempotency_key:
        request_meta['idempotency_key'] = str(idempotency_key)
    if existing_job and existing_job.status == ClassificationJob.STATUS_FAILED and retry_failed:
        request_meta['retry_of_job_id'] = existing_job.id
    if scope:
        request_meta['scope'] = scope
    
    try:
        job_id = AsyncBatchProcessor.start_classification_job(valid_ids, request_meta=request_meta)
        return _json_success({
            'success': True,
            'job_id': job_id,
            'total_count': len(valid_ids),
            'status': ClassificationJob.STATUS_PENDING,
            'reused': False,
            'request_signature': signature
        })
    except Exception as e:
        return _json_error(str(e), code="CLASSIFICATION_START_FAILED", status=500)


@ai_bp.route('/classify/status/<int:job_id>')
def get_classification_status(job_id):
    """분류 작업 상태 조회 (Polling용)"""
    user = current_user()
    job = db.session.get(ClassificationJob, job_id)
    if not job:
        return _json_error("작업을 찾을 수 없습니다.", code="JOB_NOT_FOUND", status=404)
    if not _job_visible_to_user(job, user):
        return _json_error("작업을 찾을 수 없습니다.", code="JOB_NOT_FOUND", status=404)
    
    request_meta, _ = parse_job_payload(job.result_json)
    
    return _json_success({
        'success': True,
        'status': job.status,
        'total_count': job.total_count,
        'processed_count': job.processed_count,
        'success_count': job.success_count,
        'failed_count': job.failed_count,
        'progress_percent': job.progress_percent,
        'is_complete': job.is_complete,
        'error_message': job.error_message,
        'can_cancel': job.status in (
            ClassificationJob.STATUS_PENDING,
            ClassificationJob.STATUS_PROCESSING,
        ),
        'request_signature': request_meta.get('signature'),
        'idempotency_key': request_meta.get('idempotency_key')
    })


@ai_bp.route('/classify/cancel/<int:job_id>', methods=['POST'])
def cancel_classification(job_id):
    """분류 작업 취소 요청."""
    user = current_user()
    job = db.session.get(ClassificationJob, job_id)
    if not job:
        return _json_error("작업을 찾을 수 없습니다.", code="JOB_NOT_FOUND", status=404)
    if not _job_visible_to_user(job, user):
        return _json_error("작업을 찾을 수 없습니다.", code="JOB_NOT_FOUND", status=404)

    if job.status in (
        ClassificationJob.STATUS_COMPLETED,
        ClassificationJob.STATUS_CANCELLED,
        ClassificationJob.STATUS_FAILED,
    ):
        return _json_success({
            'success': True,
            'job_id': job.id,
            'status': job.status,
            'already_complete': True,
        })

    job.status = ClassificationJob.STATUS_CANCELLED
    job.completed_at = datetime.utcnow()
    db.session.commit()

    return _json_success({
        'success': True,
        'job_id': job.id,
        'status': job.status,
        'already_complete': False,
    })


@ai_bp.route('/classify/result/<int:job_id>')
def get_classification_result(job_id):
    """분류 결과 조회 (Preview 데이터)"""
    user = current_user()
    job = db.session.get(ClassificationJob, job_id)
    if not job:
        return _json_error("작업을 찾을 수 없습니다.", code="JOB_NOT_FOUND", status=404)
    if not _job_visible_to_user(job, user):
        return _json_error("작업을 찾을 수 없습니다.", code="JOB_NOT_FOUND", status=404)
    
    if not job.is_complete:
        return _json_error(
            "작업이 아직 완료되지 않았습니다.", code="JOB_NOT_COMPLETE", status=400
        )
    
    if job.status == ClassificationJob.STATUS_FAILED:
        return _json_error(
            job.error_message or "작업 실패", code="JOB_FAILED", status=500
        )
    
    request_meta, results = parse_job_payload(job.result_json)
    if not results:
        results = []
    
    # 블록별로 그룹화
    blocks_map = {}
    no_match_list = []
    
    for r in results:
        if r.get('no_match') or not r.get('lecture_id'):
            no_match_list.append(r)
        else:
            block_name = r.get('block_name', '미지정')
            if block_name not in blocks_map:
                blocks_map[block_name] = {
                    'block_name': block_name,
                    'lectures': {}
                }
            
            lecture_title = r.get('lecture_title', '미지정')
            lecture_id = r.get('lecture_id')
            
            if lecture_id not in blocks_map[block_name]['lectures']:
                blocks_map[block_name]['lectures'][lecture_id] = {
                    'lecture_id': lecture_id,
                    'lecture_title': lecture_title,
                    'questions': []
                }
            
            blocks_map[block_name]['lectures'][lecture_id]['questions'].append(r)
    
    # 정렬 및 리스트 변환
    grouped_results = []
    for block_name in sorted(blocks_map.keys()):
        block_data = blocks_map[block_name]
        lectures_list = sorted(
            block_data['lectures'].values(),
            key=lambda x: x['lecture_title']
        )
        grouped_results.append({
            'block_name': block_name,
            'lectures': lectures_list
        })
    
    return _json_success({
        'success': True,
        'job_id': job_id,
        'grouped_results': grouped_results,
        'no_match_list': no_match_list,
        'summary': {
            'total': job.total_count,
            'success': job.success_count,
            'failed': job.failed_count,
            'no_match': len(no_match_list)
        },
        'request_signature': request_meta.get('signature')
    })


@ai_bp.route('/classify/apply', methods=['POST'])
def apply_classification():
    """분류 결과 적용 (사용자 확인 후)"""
    user = current_user()
    data = request.get_json()
    if not data:
        return _json_error("데이터가 없습니다.", code="INVALID_PAYLOAD", status=400)
    
    job_id = data.get('job_id')
    question_ids = data.get('question_ids', [])
    
    if not job_id:
        return _json_error("job_id가 필요합니다.", code="JOB_ID_REQUIRED", status=400)
    
    if not question_ids:
        return _json_error(
            "적용할 문제가 없습니다.", code="QUESTION_IDS_REQUIRED", status=400
        )

    job = db.session.get(ClassificationJob, job_id)
    if not job or not _job_visible_to_user(job, user):
        return _json_error("작업을 찾을 수 없습니다.", code="JOB_NOT_FOUND", status=404)

    request_meta, _ = parse_job_payload(job.result_json)
    super_unrestricted_apply = bool(
        request_meta.get("super_classify") and _is_super_unrestricted_user(user)
    )
    question_query = (
        Question.query
        if super_unrestricted_apply
        else scope_query(Question.query, Question, user)
    )
    valid_ids = [
        q.id
        for q in question_query
        .filter(Question.id.in_(question_ids))
        .all()
    ]
    if not valid_ids:
        return _json_error(
            "유효한 문제가 없습니다.", code="VALID_QUESTIONS_REQUIRED", status=400
        )
    
    try:
        apply_mode = data.get('apply_mode') or data.get('applyMode') or 'all'
        applied_count, apply_report = apply_classification_results(
            valid_ids,
            job_id,
            apply_mode=apply_mode,
            return_report=True,
        )
        diagnostics = build_job_diagnostics(
            job,
            question_ids=valid_ids,
            include_rows=False,
        )
        current_app.logger.warning(
            "CLASSIFIER_APPLY_SUMMARY job_id=%s requested=%s applied=%s no_match=%s out_of_candidates=%s missing_result=%s",
            job_id,
            len(valid_ids),
            applied_count,
            diagnostics.get("summary", {}).get("no_match_count"),
            diagnostics.get("summary", {}).get("out_of_candidates_count"),
            diagnostics.get("summary", {}).get("missing_result_count"),
        )
        return _json_success({
            'success': True,
            'applied_count': applied_count,
            'requested_count': len(valid_ids),
            'apply_report': apply_report,
            'diagnostics': diagnostics.get('summary', {})
        })
    except Exception as e:
        return _json_error(str(e), code="CLASSIFICATION_APPLY_FAILED", status=500)


@ai_bp.route('/classify/diagnostics/<int:job_id>')
def get_classification_diagnostics(job_id):
    """분류 작업 진단 요약 조회 (원인 분석용)."""
    user = current_user()
    job = db.session.get(ClassificationJob, job_id)
    if not job:
        return _json_error("작업을 찾을 수 없습니다.", code="JOB_NOT_FOUND", status=404)
    if not _job_visible_to_user(job, user):
        return _json_error("작업을 찾을 수 없습니다.", code="JOB_NOT_FOUND", status=404)

    raw_question_ids = request.args.getlist('question_id')
    if not raw_question_ids:
        csv_ids = request.args.get('question_ids', '')
        if csv_ids:
            raw_question_ids = [part.strip() for part in csv_ids.split(',') if part.strip()]

    question_ids = []
    for raw in raw_question_ids:
        try:
            question_ids.append(int(raw))
        except (TypeError, ValueError):
            continue

    include_rows = parse_bool(request.args.get('include_rows'), True)
    try:
        row_limit = int(request.args.get('row_limit', 200))
    except (TypeError, ValueError):
        row_limit = 200
    row_limit = max(0, min(row_limit, 2000))

    diagnostics = build_job_diagnostics(
        job,
        question_ids=question_ids or None,
        include_rows=include_rows,
        row_limit=row_limit,
    )

    return _json_success({
        'success': True,
        'diagnostics': diagnostics,
    })


@ai_bp.route('/classify/recent')
def get_recent_jobs():
    """최근 AI 분류 작업 목록 조회"""
    user = current_user()
    unrestricted_user = _is_super_unrestricted_user(user)
    # 최근 7일 이내, 최대 10개의 작업을 가져옴
    week_ago = datetime.utcnow() - timedelta(days=7)
    
    jobs = ClassificationJob.query.filter(
        ClassificationJob.created_at >= week_ago
    ).order_by(ClassificationJob.created_at.desc()).limit(10).all()

    visible_jobs = []
    request_meta_map = {}
    exam_ids = set()
    block_ids = set()

    def _to_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    for job in jobs:
        if not _job_visible_to_user(job, user):
            continue
        request_meta, _ = parse_job_payload(job.result_json)
        request_meta_map[job.id] = request_meta

        exam_id = _to_int(request_meta.get("exam_id"))
        if exam_id is not None:
            exam_ids.add(exam_id)

        scope = request_meta.get("scope")
        block_id = None
        if isinstance(scope, dict):
            block_id = _to_int(scope.get("block_id") or scope.get("blockId"))
        if block_id is not None:
            block_ids.add(block_id)

        visible_jobs.append(job)

    exam_title_map = {}
    if exam_ids:
        exam_query = (
            PreviousExam.query
            if unrestricted_user
            else scope_query(PreviousExam.query, PreviousExam, user)
        )
        exams = exam_query.filter(PreviousExam.id.in_(exam_ids)).all()
        exam_title_map = {
            exam.id: (exam.title or f"Exam {exam.id}")
            for exam in exams
        }

    block_name_map = {}
    if block_ids:
        block_query = (
            Block.query
            if unrestricted_user
            else scope_query(Block.query, Block, user, include_public=True)
        )
        blocks = block_query.filter(Block.id.in_(block_ids)).all()
        for block in blocks:
            subject_name = (
                block.subject_ref.name if block.subject_ref else block.subject
            )
            if subject_name:
                block_name_map[block.id] = f"{subject_name} · {block.name}"
            else:
                block_name_map[block.id] = block.name

    result = []
    for job in visible_jobs:
        request_meta = request_meta_map.get(job.id) or {}
        exam_id = _to_int(request_meta.get("exam_id"))
        scope = request_meta.get("scope")
        block_id = None
        if isinstance(scope, dict):
            block_id = _to_int(scope.get("block_id") or scope.get("blockId"))
        status_label = {
            'pending': '대기중',
            'processing': '진행중',
            'completed': '완료',
            'cancelled': '취소됨',
            'failed': '실패'
        }.get(job.status, job.status)
        
        result.append({
            'id': job.id,
            'created_at': _format_kst(job.created_at),
            'status': job.status,
            'status_label': status_label,
            'total_count': job.total_count,
            'success_count': job.success_count,
            'is_complete': job.is_complete,
            'exam_id': exam_id,
            'exam_title': exam_title_map.get(exam_id),
            'block_id': block_id,
            'block_name': block_name_map.get(block_id),
            'super_classify': parse_bool(request_meta.get("super_classify"), False),
        })
    
    return _json_success({
        'success': True,
        'jobs': result
    })


@ai_bp.route('/classify/preview/<int:job_id>')
def preview_classification(job_id):
    """분류 결과 미리보기 페이지"""
    user = current_user()
    job = ClassificationJob.query.get_or_404(job_id)
    if not _job_visible_to_user(job, user):
        return _json_error("작업을 찾을 수 없습니다.", code="JOB_NOT_FOUND", status=404)
    blocks = scope_model(Block, user, include_public=True).order_by(*block_ordering()).all()
    
    return render_template('exam/ai_classification_preview.html',
                         job=job,
                         blocks=blocks)


@ai_bp.route('/classify/super/start', methods=['POST'])
def start_super_classification():
    """Super AI 분류 작업 시작 (시험 1개 + 블록 1개 기반, gemini-3.1-pro-preview)"""
    user = current_user()
    if not GENAI_AVAILABLE:
        return _json_error(
            "google-genai 패키지가 설치되지 않았습니다.",
            code="GENAI_NOT_AVAILABLE",
            status=500,
        )

    data = request.get_json()
    if data is None:
        return _json_error("데이터가 없습니다.", code="INVALID_PAYLOAD", status=400)

    exam_id = data.get('exam_id') or data.get('examId')
    if not exam_id:
        return _json_error(
            "exam_id가 필요합니다.", code="EXAM_ID_REQUIRED", status=400
        )

    try:
        exam_id = int(exam_id)
    except (TypeError, ValueError):
        return _json_error(
            "유효하지 않은 exam_id입니다.", code="INVALID_EXAM_ID", status=400
        )

    unrestricted_user = _is_super_unrestricted_user(user)

    exam = (
        db.session.get(PreviousExam, exam_id)
        if unrestricted_user
        else get_scoped_by_id(PreviousExam, exam_id, user)
    )
    if not exam:
        return _json_error(
            "시험을 찾을 수 없습니다.", code="EXAM_NOT_FOUND", status=404
        )

    question_query = Question.query if unrestricted_user else scope_query(
        Question.query, Question, user
    )
    exam_questions = (
        question_query
        .filter(Question.exam_id == exam_id)
        .order_by(Question.question_number)
        .all()
    )
    question_ids = [q.id for q in exam_questions]
    if not question_ids:
        return _json_error("시험에 문제가 없습니다.", code="NO_QUESTIONS", status=400)

    def _pick_scope_value(payload, snake_key, camel_key):
        if snake_key in payload:
            return payload.get(snake_key)
        if camel_key in payload:
            return payload.get(camel_key)
        return None

    raw_scope = data.get('scope')
    if not isinstance(raw_scope, dict):
        raw_scope = {}
    block_id_raw = _pick_scope_value(data, 'block_id', 'blockId')
    if block_id_raw is None:
        block_id_raw = _pick_scope_value(raw_scope, 'block_id', 'blockId')
    if block_id_raw in (None, ""):
        return _json_error(
            "Super AI 분류를 위해 블록을 선택하세요.",
            code="SUPER_BLOCK_ID_REQUIRED",
            status=400,
        )
    try:
        block_id_value = int(block_id_raw)
    except (TypeError, ValueError):
        return _json_error(
            "유효하지 않은 block_id입니다.",
            code="SUPER_INVALID_BLOCK_ID",
            status=400,
        )

    block = (
        db.session.get(Block, block_id_value)
        if unrestricted_user
        else get_scoped_by_id(Block, block_id_value, user, include_public=True)
    )
    if not block:
        return _json_error(
            "블록을 찾을 수 없습니다.",
            code="SUPER_BLOCK_NOT_FOUND",
            status=404,
        )

    def _normalize_subject(value):
        if value is None:
            return ""
        return " ".join(str(value).strip().lower().split())

    exam_subject = _normalize_subject(exam.subject)
    block_subject_value = block.subject_ref.name if block.subject_ref else block.subject
    block_subject = _normalize_subject(block_subject_value)

    if not exam_subject:
        return _json_error(
            "시험 과목(subject)이 비어 있어 블록 매칭을 검증할 수 없습니다.",
            code="SUPER_EXAM_SUBJECT_REQUIRED",
            status=400,
        )
    if not block_subject:
        return _json_error(
            "선택한 블록에 과목(subject)이 없어 사용할 수 없습니다.",
            code="SUPER_BLOCK_SUBJECT_REQUIRED",
            status=400,
        )
    if exam_subject != block_subject:
        return _json_error(
            "선택한 블록의 과목이 시험 과목과 다릅니다.",
            code="SUPER_SCOPE_SUBJECT_MISMATCH",
            status=400,
            payload={
                "exam_subject": exam.subject,
                "block_subject": block_subject_value,
                "block_id": block.id,
            },
        )

    normalized_scope = normalize_classification_scope(
        {"block_id": block.id, "include_descendants": True}
    )
    if unrestricted_user:
        # Trusted local override users can run super-classify across all records
        # in non-production, so do not scope lecture lookup to public-only data.
        lecture_ids = [
            int(lecture_id)
            for (lecture_id,) in (
                db.session.query(Lecture.id)
                .filter(Lecture.block_id == block.id)
                .all()
            )
        ]
        scope = {
            "block_id": block.id,
            "include_descendants": True,
            "lecture_ids": sorted({int(lecture_id) for lecture_id in (lecture_ids or [])}),
        }
    else:
        scope = resolve_scope_lecture_ids(
            normalized_scope,
            user=user,
            include_public=True,
        )
        scope["block_id"] = block.id
        scope["include_descendants"] = True
        scope["lecture_ids"] = sorted(
            {int(lecture_id) for lecture_id in (scope.get("lecture_ids") or [])}
        )

    lecture_ids = scope.get('lecture_ids') or []
    if not lecture_ids:
        return _json_error(
            "분류 가능한 강의가 없습니다.", code="NO_AVAILABLE_LECTURES", status=400
        )

    idempotency_key = data.get('idempotency_key') or data.get('idempotencyKey')
    force = parse_bool(data.get('force'), False)
    retry_failed = parse_bool(
        data.get('retry') or data.get('retry_failed') or data.get('retryFailed'),
        False,
    )
    retry_missing = parse_bool(
        data.get('retry_missing') or data.get('retryMissing'),
        True,
    )
    signature = _build_super_request_signature(
        exam_id,
        question_ids,
        idempotency_key=idempotency_key,
        scope=scope or None,
    )

    existing_job = None
    retry_source_job = None
    if not force:
        existing_job = _find_recent_job(signature)
        if existing_job and not _job_visible_to_user(existing_job, user):
            existing_job = None

    if existing_job and existing_job.status not in (
        ClassificationJob.STATUS_FAILED,
        ClassificationJob.STATUS_CANCELLED,
    ):
        if retry_missing and existing_job.status == ClassificationJob.STATUS_COMPLETED:
            missing_retry_ids = _super_retry_missing_question_ids(existing_job)
            if missing_retry_ids:
                retry_source_job = existing_job
                question_ids = missing_retry_ids
                signature = _build_super_request_signature(
                    exam_id,
                    question_ids,
                    idempotency_key=idempotency_key,
                    scope=scope or None,
                )
                retry_job = _find_recent_job(signature)
                if retry_job and _job_visible_to_user(retry_job, user):
                    if retry_job.status not in (
                        ClassificationJob.STATUS_FAILED,
                        ClassificationJob.STATUS_CANCELLED,
                    ):
                        return _json_success({
                            'success': True,
                            'job_id': retry_job.id,
                            'total_count': retry_job.total_count,
                            'status': retry_job.status,
                            'reused': True,
                            'request_signature': signature,
                            'super_classify': True,
                            'retry_missing': True,
                        })
            else:
                return _json_success({
                    'success': True,
                    'job_id': existing_job.id,
                    'total_count': existing_job.total_count,
                    'status': existing_job.status,
                    'reused': True,
                    'request_signature': signature,
                    'super_classify': True,
                })
        else:
            return _json_success({
                'success': True,
                'job_id': existing_job.id,
                'total_count': existing_job.total_count,
                'status': existing_job.status,
                'reused': True,
                'request_signature': signature,
                'super_classify': True,
            })
    if (
        existing_job
        and existing_job.status in (
            ClassificationJob.STATUS_FAILED,
            ClassificationJob.STATUS_CANCELLED,
        )
        and not retry_failed
    ):
        existing_job = None

    requested_at = datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
    request_meta = {
        'signature': signature,
        'question_ids': question_ids,
        'requested_at': requested_at,
        'scope_user_id': user.id,
        'super_classify': True,
        'exam_id': exam_id,
    }
    if idempotency_key:
        request_meta['idempotency_key'] = str(idempotency_key)
    if retry_source_job is not None:
        request_meta['retry_of_job_id'] = retry_source_job.id
        request_meta['retry_missing'] = True
    if existing_job and existing_job.status == ClassificationJob.STATUS_FAILED and retry_failed:
        request_meta['retry_of_job_id'] = existing_job.id
    if scope:
        request_meta['scope'] = scope

    try:
        from app.services.super_classifier import SuperClassifier

        job_id = SuperClassifier.start_super_classification_job(
            exam_id,
            request_meta=request_meta,
            lecture_ids=lecture_ids,
            question_ids=question_ids,
            block_id=block.id,
            include_descendants=True,
        )
        return _json_success({
            'success': True,
            'job_id': job_id,
            'total_count': len(question_ids),
            'status': ClassificationJob.STATUS_PENDING,
            'super_classify': True,
            'reused': False,
            'retry_missing': retry_source_job is not None,
            'request_signature': signature,
        })
    except Exception as e:
        return _json_error(
            str(e), code="SUPER_CLASSIFICATION_START_FAILED", status=500
        )


@ai_bp.route('/correct-text', methods=['POST'])
def correct_text():
    """AI 텍스트 교정 (띄어쓰기, 맞춤법)"""
    if not GENAI_AVAILABLE:
        return _json_error(
            "google-genai 패키지가 설치되지 않았습니다.",
            code="GENAI_NOT_AVAILABLE",
            status=500,
        )
    
    data = request.get_json()
    if not data or not data.get('text'):
        return _json_error("텍스트가 없습니다.", code="TEXT_REQUIRED", status=400)
    
    original_text = data['text']
    
    # Gemini API 초기화
    cfg = get_config()
    api_key = cfg.runtime.gemini_api_key or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return _json_error(
            "GEMINI_API_KEY 또는 GOOGLE_API_KEY가 설정되지 않았습니다.",
            code="GEMINI_API_KEY_MISSING",
            status=500,
        )
    
    try:
        client = genai.Client(api_key=api_key)
        model_name = "gemini-2.5-flash-lite"
        
        prompt = f"""당신은 의학 시험 문제 전문 교정사입니다. 아래 텍스트의 띄어쓰기와 맞춤법 오류를 수정해주세요.

## 규칙
1. 띄어쓰기 오류만 수정하세요 (예: "심장 근육세포" → "심장근육세포" 또는 그 반대).
2. 명백한 오타만 수정하세요.
3. 의학/생물학 전문 용어, 영어 표현, 숫자는 절대 변경하지 마세요.
4. 내용을 추가하거나 삭제하지 마세요.
5. 교정된 텍스트만 출력하세요. 설명이나 추가 문구는 넣지 마세요.

## 원본 텍스트
{original_text}

## 교정된 텍스트"""
        
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                top_p=0.9,
                max_output_tokens=2000,
            )
        )
        
        corrected_text = response.text.strip()
        
        return _json_success({
            'success': True,
            'original': original_text,
            'corrected': corrected_text
        })
        
    except Exception as e:
        return _json_error(str(e), code="TEXT_CORRECTION_FAILED", status=500)
