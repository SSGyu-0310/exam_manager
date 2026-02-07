"""JSON API for exam screens (unclassified queue)."""

from flask import Blueprint, request, jsonify
from sqlalchemy import or_
from sqlalchemy.orm import selectinload
from config import get_config
from app.domain.models import HealthStatus
from app.models import Block, Lecture, PreviousExam, Question
from app.routes.api_manage import (
    _build_block_counts,
    _build_exam_counts,
    _build_lecture_counts,
    _build_choices_map,
    _block_payload,
    _exam_payload,
    _lecture_payload,
    _question_payload,
    ok,
)
from app.services.folder_scope import parse_bool, resolve_lecture_ids
from app.services.user_scope import (
    attach_current_user,
    current_user,
    scope_model,
    scope_query,
)
from app.services.block_sort import block_ordering

api_exam_bp = Blueprint("api_exam", __name__, url_prefix="/api/exam")


@api_exam_bp.before_request
def restrict_to_local_admin():
    if not get_config().runtime.local_admin_only:
        return None
    remote_addr = request.remote_addr or ""
    if remote_addr not in {"127.0.0.1", "::1"}:
        from flask import abort

        abort(404)
    return None


@api_exam_bp.before_request
def attach_user():
    return attach_current_user(require=True)


@api_exam_bp.get("/health")
def health_check():
    health = HealthStatus(status="ok", schema_version="v1")
    return jsonify(health.to_dict())


@api_exam_bp.get("/unclassified")
def list_unclassified():
    user = current_user()
    status = request.args.get("status", "all")
    exam_id = request.args.get("examId")
    query = request.args.get("query", "").strip()
    block_id = request.args.get("blockId") or request.args.get("block_id")
    folder_id = request.args.get("folderId") or request.args.get("folder_id")
    include_descendants = parse_bool(
        request.args.get("includeDescendants")
        or request.args.get("include_descendants"),
        True,
    )
    filter_scope = parse_bool(
        request.args.get("filterScope") or request.args.get("filter_scope"),
        False,
    )

    try:
        limit = int(request.args.get("limit", 200))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        limit = 200
        offset = 0

    q = scope_query(Question.query, Question, user).options(
        selectinload(Question.exam), selectinload(Question.lecture)
    )
    if status == "unclassified":
        q = q.filter_by(is_classified=False)
    elif status == "classified":
        q = q.filter_by(is_classified=True)
    if exam_id:
        try:
            exam_id_value = int(exam_id)
            q = q.filter(Question.exam_id == exam_id_value)
        except ValueError:
            return jsonify(
                {"ok": False, "code": "INVALID_EXAM_ID", "message": "Invalid exam id."}
            ), 400
    if query:
        q = q.filter(Question.content.contains(query))

    block_id_value = None
    if block_id:
        try:
            block_id_value = int(block_id)
        except ValueError:
            return jsonify(
                {
                    "ok": False,
                    "code": "INVALID_BLOCK_ID",
                    "message": "Invalid block id.",
                }
            ), 400
    folder_id_value = None
    if folder_id:
        try:
            folder_id_value = int(folder_id)
        except ValueError:
            return jsonify(
                {
                    "ok": False,
                    "code": "INVALID_FOLDER_ID",
                    "message": "Invalid folder id.",
                }
            ), 400

    lecture_ids = resolve_lecture_ids(
        block_id_value,
        folder_id_value,
        include_descendants,
        user=user,
        include_public=True,
    )
    if filter_scope and lecture_ids is not None:
        if status == "classified":
            q = q.filter(Question.lecture_id.in_(lecture_ids))
        elif status == "all":
            q = q.filter(
                or_(Question.lecture_id.is_(None), Question.lecture_id.in_(lecture_ids))
            )

    total = q.count()
    questions = (
        q.order_by(Question.is_classified, Question.exam_id, Question.question_number)
        .offset(offset)
        .limit(limit)
        .all()
    )
    choices_map = _build_choices_map([question.id for question in questions])

    blocks = (
        scope_model(Block, user, include_public=True)
        .options(selectinload(Block.subject_ref))
        .order_by(*block_ordering())
        .all()
    )
    block_ids = [block.id for block in blocks]
    exams = scope_model(PreviousExam, user).order_by(
        PreviousExam.created_at.desc()
    ).all()
    block_lecture_counts, block_question_counts = _build_block_counts(
        block_ids, user
    )
    exam_counts = _build_exam_counts([exam.id for exam in exams], user)
    unclassified_count = scope_query(Question.query, Question, user).filter_by(
        is_classified=False
    ).count()
    lectures_by_block = {block_id: [] for block_id in block_ids}
    if block_ids:
        lecture_rows = (
            scope_model(Lecture, user, include_public=True)
            .filter(Lecture.block_id.in_(block_ids))
            .order_by(Lecture.block_id, Lecture.order, Lecture.id)
            .all()
        )
        for lecture in lecture_rows:
            lectures_by_block.setdefault(lecture.block_id, []).append(
                {"id": lecture.id, "title": lecture.title}
            )

    candidate_lectures = None
    if lecture_ids is not None:
        if lecture_ids:
            lecture_rows = (
                scope_model(Lecture, user, include_public=True)
                .options(selectinload(Lecture.block).selectinload(Block.subject_ref))
                .filter(Lecture.id.in_(lecture_ids))
                .order_by(Lecture.order)
                .all()
            )
            lecture_counts, classified_counts = _build_lecture_counts(
                [lecture.id for lecture in lecture_rows], user
            )
            candidate_lectures = [
                _lecture_payload(lecture, lecture_counts, classified_counts)
                for lecture in lecture_rows
            ]
        else:
            candidate_lectures = []

    return ok(
        {
            "items": [
                _question_payload(question, choices_map) for question in questions
            ],
            "total": total,
            "offset": offset,
            "limit": limit,
            "unclassifiedCount": unclassified_count,
            "blocks": [
                {
                    **_block_payload(
                        block, block_lecture_counts, block_question_counts
                    ),
                    "lectures": lectures_by_block.get(block.id, []),
                }
                for block in blocks
            ],
            "exams": [_exam_payload(exam, exam_counts) for exam in exams],
            "scope": {
                "blockId": block_id_value,
                "folderId": folder_id_value,
                "includeDescendants": include_descendants,
                "filterScope": filter_scope,
                "lectureIds": lecture_ids,
            },
            "candidateLectures": candidate_lectures,
        }
    )
