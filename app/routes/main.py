"""메인 페이지 Blueprint"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_jwt_extended import create_access_token, set_access_cookies, unset_jwt_cookies
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.models import Block, Lecture, PreviousExam, Question, User

main_bp = Blueprint('main', __name__)

_LOCALHOSTS = {"127.0.0.1", "::1"}


def _legacy_ui_local_only() -> bool:
    return bool(current_app.config.get("LEGACY_UI_LOCAL_ONLY", True))


def _is_local_request() -> bool:
    return (request.remote_addr or "") in _LOCALHOSTS


def _ensure_legacy_access_enabled():
    if not _legacy_ui_local_only():
        return
    if _is_local_request():
        return
    abort(404)


def _safe_next_path(raw_next: str | None) -> str:
    candidate = (raw_next or "").strip()
    if not candidate:
        return "/manage"
    parsed = urlsplit(candidate)
    if parsed.scheme or parsed.netloc:
        return "/manage"
    if not candidate.startswith("/") or candidate.startswith("//"):
        return "/manage"
    return candidate


def _get_or_create_legacy_user() -> User:
    trusted_email = (
        current_app.config.get("LEGACY_UI_TRUSTED_EMAIL") or "hisukgyu@gmail.com"
    ).strip().lower()
    user = User.query.filter_by(email=trusted_email).first()
    if user is not None:
        return user

    user = User(email=trusted_email)
    user.set_password(secrets.token_urlsafe(24))
    db.session.add(user)
    db.session.commit()
    return user


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


@main_bp.route("/legacy-access", methods=["GET", "POST"])
def legacy_access():
    _ensure_legacy_access_enabled()

    next_path = _safe_next_path(request.values.get("next"))
    pin_value = str(current_app.config.get("LEGACY_UI_PIN", "4242"))
    pin_hint = pin_value if pin_value == "4242" else None

    if request.method == "POST":
        submitted_pin = (request.form.get("pin") or "").strip()
        if submitted_pin != pin_value:
            flash("인증번호가 올바르지 않습니다.", "error")
            return render_template(
                "legacy_access.html",
                next_path=next_path,
                pin_hint=pin_hint,
            ), 401

        user = _get_or_create_legacy_user()
        access_token = create_access_token(identity=str(user.id))
        response = redirect(next_path)
        set_access_cookies(response, access_token)
        flash(f"{user.email} 계정으로 Flask UI에 로그인했습니다.", "success")
        return response

    return render_template(
        "legacy_access.html",
        next_path=next_path,
        pin_hint=pin_hint,
    )


@main_bp.route("/legacy-access/logout", methods=["POST"])
def legacy_access_logout():
    _ensure_legacy_access_enabled()
    response = redirect(url_for("main.legacy_access"))
    unset_jwt_cookies(response)
    flash("Flask UI 로그아웃 완료.", "success")
    return response


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
