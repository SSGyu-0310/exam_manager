from __future__ import annotations

from typing import Optional

from flask import current_app, request, g, redirect, url_for, flash
from flask_jwt_extended import (
    get_jwt_identity,
    verify_jwt_in_request,
    unset_jwt_cookies,
)
from flask_jwt_extended.exceptions import JWTExtendedException, NoAuthorizationError
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from sqlalchemy import or_, false

from app import db
from app.models import User
from app.services.api_response import error_response as _error_response

_LOCALHOSTS = {"127.0.0.1", "::1"}


def _is_local_admin_request() -> bool:
    if not current_app.config.get("LOCAL_ADMIN_ONLY"):
        return False
    if current_app.config.get("ENV_NAME") == "production":
        return False
    if not current_app.debug:
        return False
    return (request.remote_addr or "") in _LOCALHOSTS


def _load_admin_user() -> Optional[User]:
    return User.query.filter_by(is_admin=True).order_by(User.id).first()


def _unauthorized(message: str = "Authentication required."):
    return _error_response(
        message=message,
        code="UNAUTHORIZED",
        status=401,
        legacy={"msg": message},
    )


def _normalized_next_path() -> str:
    path = request.path or "/"
    query = request.query_string.decode("utf-8", errors="ignore").strip()
    if query:
        return f"{path}?{query}"
    return path


def _is_browser_html_request() -> bool:
    accept = request.accept_mimetypes
    best = accept.best_match(["text/html", "application/json"])
    if best == "text/html":
        return True

    raw_accept = (request.headers.get("Accept") or "").lower()
    if "text/html" in raw_accept:
        return True

    if request.method in {"GET", "HEAD"} and not raw_accept:
        return True
    return False


def _is_browser_form_request() -> bool:
    if request.method in {"GET", "HEAD"}:
        return False
    if request.is_json:
        return False

    content_type = (request.content_type or "").lower()
    if content_type.startswith("application/x-www-form-urlencoded"):
        return True
    if content_type.startswith("multipart/form-data"):
        return True
    return _is_browser_html_request()


def should_redirect_to_legacy_access(require: bool, error) -> bool:
    if not require or error is None:
        return False
    if request.path.startswith("/api/"):
        return False
    if request.path.startswith("/legacy-access"):
        return False
    if request.method == "OPTIONS":
        return False
    return _is_browser_html_request() or _is_browser_form_request()


def build_legacy_access_redirect(message: str | None = None):
    response = redirect(
        url_for("main.legacy_access", next=_normalized_next_path())
    )
    unset_jwt_cookies(response)
    if message:
        flash(message, "error")
    return response


def attach_current_user(require: bool = False):
    """Attach current user to request context (g.current_user)."""
    user = None
    error = None
    redirect_message = None

    try:
        verify_jwt_in_request(optional=not require)
    except NoAuthorizationError:
        if require:
            redirect_message = "로그인이 필요합니다."
            error = _unauthorized()
    except (JWTExtendedException, ExpiredSignatureError, InvalidTokenError) as exc:
        redirect_message = "세션이 만료되었거나 유효하지 않습니다. 다시 로그인해주세요."
        error = _unauthorized(str(exc))
    else:
        identity = get_jwt_identity()
        if identity is not None:
            try:
                user = db.session.get(User, int(identity))
            except (TypeError, ValueError):
                user = None

    if user is None and _is_local_admin_request():
        user = _load_admin_user()
        error = None

    g.current_user = user

    if should_redirect_to_legacy_access(require, error):
        return build_legacy_access_redirect(redirect_message)

    if user is None and error is not None:
        return error
    if require and user is None:
        return _unauthorized()
    return None


def current_user() -> Optional[User]:
    return getattr(g, "current_user", None)


def require_user():
    user = current_user()
    if user is None:
        return None, _unauthorized()
    return user, None


def scope_query(query, model, user: Optional[User], include_public: bool = False):
    if user is None:
        if include_public:
            return query.filter(model.user_id.is_(None))
        return query.filter(false())
    if getattr(user, "is_admin", False):
        return query
    if include_public:
        return query.filter(or_(model.user_id == user.id, model.user_id.is_(None)))
    return query.filter(model.user_id == user.id)


def scope_model(model, user: Optional[User], include_public: bool = False):
    return scope_query(model.query, model, user, include_public=include_public)


def get_scoped_by_id(
    model, record_id: int, user: Optional[User], include_public: bool = False
):
    return (
        scope_model(model, user, include_public=include_public)
        .filter(model.id == record_id)
        .first()
    )
