"""메인 페이지 Blueprint"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flask import Blueprint, current_app, jsonify, render_template
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.models import Block, Lecture, PreviousExam, Question

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """대시보드 메인 페이지"""
    if current_app.config.get("APP_MODE") == "prototype":
        return render_template("prototype/index.html", **_build_prototype_context())
    return render_template('index.html')


@main_bp.route('/prototype')
def prototype_home():
    """프로토타입 전용 대시보드"""
    return render_template("prototype/index.html", **_build_prototype_context())


@main_bp.route('/health')
def health():
    """헬스 체크: 앱/DB 상태 + 기본 카운트"""
    payload = _build_prototype_context()
    return jsonify(
        {
            "app_mode": payload["app_mode"],
            "db_ok": payload["db_ok"],
            "db_error": payload["db_error"],
            "counts": payload["counts"],
        }
    )


@dataclass
class _CountResult:
    value: int | None
    error: str | None = None


def _db_ping() -> _CountResult:
    try:
        db.session.execute(text("SELECT 1"))
        return _CountResult(value=1)
    except SQLAlchemyError as exc:
        db.session.rollback()
        return _CountResult(value=None, error=str(exc))


def _safe_count(model: Any) -> _CountResult:
    try:
        return _CountResult(value=model.query.count())
    except SQLAlchemyError as exc:
        db.session.rollback()
        return _CountResult(value=None, error=str(exc))


def _safe_recent(query, limit: int = 5):
    try:
        return query.limit(limit).all()
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.warning("prototype recent query failed: %s", exc)
        return []


def _build_prototype_context() -> dict[str, Any]:
    ping = _db_ping()
    db_ok = ping.error is None
    counts = {
        "blocks": None,
        "lectures": None,
        "exams": None,
        "questions": None,
    }
    errors = {}
    if db_ok:
        for key, model in (
            ("blocks", Block),
            ("lectures", Lecture),
            ("exams", PreviousExam),
            ("questions", Question),
        ):
            result = _safe_count(model)
            counts[key] = result.value
            if result.error:
                errors[key] = result.error

    recent_lectures = []
    recent_exams = []
    recent_questions = []
    if db_ok:
        recent_lectures = _safe_recent(
            Lecture.query.order_by(Lecture.created_at.desc())
        )
        recent_exams = _safe_recent(
            PreviousExam.query.order_by(PreviousExam.created_at.desc())
        )
        recent_questions = _safe_recent(
            Question.query.order_by(Question.created_at.desc())
        )

    return {
        "app_mode": current_app.config.get("APP_MODE", "full"),
        "db_ok": db_ok,
        "db_error": ping.error,
        "counts": counts,
        "count_errors": errors,
        "recent_lectures": recent_lectures,
        "recent_exams": recent_exams,
        "recent_questions": recent_questions,
    }
