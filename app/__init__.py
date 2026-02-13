"""Flask 애플리케이션 팩토리"""

import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, g, request
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt,
    get_jwt_identity,
    set_access_cookies,
    verify_jwt_in_request,
)
from flask_sqlalchemy import SQLAlchemy
from markupsafe import Markup, escape

from config import get_config, set_config_name
from config.base import DEFAULT_SECRET_KEY, DEFAULT_JWT_SECRET_KEY

# SQLAlchemy 인스턴스 (다른 모듈에서 import 가능)
db = SQLAlchemy()
jwt = JWTManager()
_MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_REQUEST_LOGGER_NAME = "exam_manager.request"
_REQUEST_ID_HEADER = "X-Request-ID"
_ERROR_CODES = ("error_code", "code")


def _get_request_logger() -> logging.Logger:
    logger = logging.getLogger(_REQUEST_LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def _resolve_request_id() -> str:
    request_id = (request.headers.get(_REQUEST_ID_HEADER) or "").strip()
    if request_id:
        return request_id[:128]
    return uuid.uuid4().hex


def _resolve_route() -> str:
    rule = getattr(request, "url_rule", None)
    if rule and getattr(rule, "rule", None):
        return str(rule.rule)
    return request.path


def _resolve_error_code_from_response(response) -> str | None:
    status_code = int(getattr(response, "status_code", 0) or 0)
    if status_code < 400:
        return None

    if response.is_json:
        payload = response.get_json(silent=True)
        if isinstance(payload, dict):
            for key in _ERROR_CODES:
                value = payload.get(key)
                if value not in (None, ""):
                    return str(value)

    return f"HTTP_{status_code}"


def _log_request(
    request_logger: logging.Logger,
    *,
    request_id: str,
    route: str,
    status: int,
    latency: float,
    error_code: str | None,
) -> None:
    request_logger.info(
        json.dumps(
            {
                "request_id": request_id,
                "route": route,
                "status": status,
                "latency": latency,
                "error_code": error_code,
            },
            separators=(",", ":"),
        )
    )


def _env_int(name: str, default: int, minimum: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    if minimum is not None and value < minimum:
        return minimum
    return value


def render_markdown_images(value):
    """Render markdown image syntax to HTML img tags, escaping other text."""
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    parts = []
    last_index = 0
    for match in _MARKDOWN_IMAGE_PATTERN.finditer(text):
        parts.append(escape(text[last_index : match.start()]))
        alt_text = escape(match.group(1))
        url = escape(match.group(2).strip())
        parts.append(f'<img src="{url}" alt="{alt_text}" class="markdown-image">')
        last_index = match.end()
    parts.append(escape(text[last_index:]))
    return Markup("".join(parts))


def create_app(
    config_name="default",
    db_uri_override: str | None = None,
    skip_migration_check: bool = False,
):
    """
    Flask 애플리케이션 팩토리

    Args:
        config_name: 설정 이름 ('development', 'production', 'default')

    Returns:
        Flask 앱 인스턴스
    """
    app = Flask(__name__)

    injected_database_url = False
    if db_uri_override and not os.environ.get("DATABASE_URL"):
        # Runtime config is Postgres-only. For explicit test/tool overrides, allow
        # config bootstrap without requiring caller-side DATABASE_URL plumbing.
        os.environ["DATABASE_URL"] = "postgresql+psycopg://placeholder:placeholder@127.0.0.1:5432/placeholder"
        injected_database_url = True

    # Set config profile name and load from new config package
    set_config_name(config_name)
    try:
        cfg = get_config()
    finally:
        if injected_database_url:
            os.environ.pop("DATABASE_URL", None)

    if config_name == "production":
        if not cfg.secret_key or cfg.secret_key == DEFAULT_SECRET_KEY:
            raise RuntimeError(
                "SECRET_KEY must be set to a non-default value in production."
            )
        if (
            not cfg.runtime.jwt_secret_key
            or cfg.runtime.jwt_secret_key == DEFAULT_JWT_SECRET_KEY
        ):
            raise RuntimeError(
                "JWT_SECRET_KEY must be set to a non-default value in production."
            )

    app.config["ENV_NAME"] = config_name
    effective_db_uri = db_uri_override or cfg.runtime.db_uri
    app.config["SQLALCHEMY_DATABASE_URI"] = effective_db_uri
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    if str(effective_db_uri).startswith("postgres"):
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "pool_pre_ping": True,
            "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "1800")),
            "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
        }
    app.config["SECRET_KEY"] = cfg.secret_key
    app.config["JWT_SECRET_KEY"] = cfg.runtime.jwt_secret_key
    app.config["JWT_TOKEN_LOCATION"] = ["headers", "cookies"]
    app.config["JWT_ACCESS_COOKIE_NAME"] = "auth_token"
    app.config["JWT_COOKIE_SAMESITE"] = "Lax"
    app.config["JWT_COOKIE_SECURE"] = cfg.runtime.jwt_cookie_secure
    jwt_access_minutes = _env_int("JWT_ACCESS_TOKEN_EXPIRES_MINUTES", 720, minimum=5)
    jwt_refresh_window_minutes = _env_int("JWT_REFRESH_WINDOW_MINUTES", 30, minimum=1)
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=jwt_access_minutes)
    app.config["JWT_REFRESH_WINDOW_MINUTES"] = jwt_refresh_window_minutes
    # HTML form posts in local/dev flows (e.g. manage delete actions) do not
    # send JWT CSRF headers. Keep strict CSRF in production only.
    app.config["JWT_COOKIE_CSRF_PROTECT"] = config_name == "production"
    app.config["LOCAL_ADMIN_ONLY"] = cfg.runtime.local_admin_only
    app.config["DB_READ_ONLY"] = cfg.runtime.db_read_only
    app.config["AUTO_BACKUP_BEFORE_WRITE"] = cfg.runtime.auto_backup_before_write
    app.config["AUTO_BACKUP_KEEP"] = cfg.runtime.auto_backup_keep
    app.config["AUTO_BACKUP_DIR"] = str(cfg.runtime.auto_backup_dir)
    app.config["ENFORCE_BACKUP_BEFORE_WRITE"] = cfg.runtime.enforce_backup_before_write
    app.config["CHECK_PENDING_MIGRATIONS"] = cfg.runtime.check_pending_migrations
    app.config["FAIL_ON_PENDING_MIGRATIONS"] = cfg.runtime.fail_on_pending_migrations
    app.config["AUTO_CREATE_DB"] = cfg.runtime.auto_create_db
    app.secret_key = cfg.secret_key
    app.config["UPLOAD_FOLDER"] = str(cfg.runtime.upload_folder)
    app.config["MAX_CONTENT_LENGTH"] = cfg.runtime.max_content_length
    app.config["KEEP_PDF_AFTER_INDEX"] = cfg.runtime.keep_pdf_after_index
    app.config["APP_MODE"] = os.getenv("APP_MODE", "full")
    # Legacy routes still read parser mode from current_app.config.
    app.config["PDF_PARSER_MODE"] = cfg.experiment.pdf_parser_mode
    app.config["CORS_ALLOWED_ORIGINS"] = cfg.runtime.cors_allowed_origins
    app.config["CORS_ALLOW_CREDENTIALS"] = True

    # Legacy config mirror: get_config() is now the single source of truth.
    # Services migrated to use get_config() directly, no full mirror needed.
    # Legacy routes using current_app.config.get() will use default values.
    if not skip_migration_check and app.config.get("CHECK_PENDING_MIGRATIONS", True):
        from app.services.migrations import check_pending_migrations

        migrations_dir = Path(__file__).resolve().parents[1] / "migrations"
        check_pending_migrations(
            app.config["SQLALCHEMY_DATABASE_URI"],
            migrations_dir,
            app.config["ENV_NAME"],
            app.logger,
            app.config.get("FAIL_ON_PENDING_MIGRATIONS", False),
        )

    # SQLAlchemy 초기화
    db.init_app(app)
    jwt.init_app(app)

    # Backward-compatible schema patch for existing DB volumes.
    with app.app_context():
        from app.services.schema_patch import (
            ensure_question_examiner_column,
            ensure_question_ai_final_lecture_column,
        )

        ensure_question_examiner_column(app.logger)
        ensure_question_ai_final_lecture_column(app.logger)

    # 업로드 디렉토리 생성
    upload_folder = app.config.get("UPLOAD_FOLDER")
    if upload_folder and not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    # Blueprint 등록
    if app.config["APP_MODE"] == "prototype":
        _register_prototype_blueprints(app)
    else:
        _register_full_blueprints(app)

    app.jinja_env.filters["md_image"] = render_markdown_images

    cors_allowed = {
        origin.strip()
        for origin in app.config.get("CORS_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    }
    request_logger = _get_request_logger()

    def _apply_cors_headers(response):
        origin = request.headers.get("Origin")
        if not origin:
            return response
        if "*" not in cors_allowed and origin not in cors_allowed:
            return response

        # Cookie auth requires explicit origin echo, not wildcard.
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        )
        request_headers = request.headers.get("Access-Control-Request-Headers")
        response.headers["Access-Control-Allow-Headers"] = (
            request_headers
            if request_headers
            else "Authorization, Content-Type, X-CSRF-TOKEN"
        )
        response.headers["Access-Control-Max-Age"] = "600"
        vary = response.headers.get("Vary")
        response.headers["Vary"] = (
            "Origin" if not vary else f"{vary}, Origin"
        )
        return response

    @app.before_request
    def mark_request_started():
        g.request_id = _resolve_request_id()
        g.request_started_at = time.perf_counter()
        g.request_logged = False

    @app.before_request
    def handle_cors_preflight():
        if request.method == "OPTIONS":
            return _apply_cors_headers(app.make_default_options_response())
        return None

    @app.after_request
    def refresh_expiring_jwt(response):
        # Keep logout explicit: do not overwrite cookie clear on logout route.
        if request.endpoint == "api_auth.logout":
            return response
        try:
            verify_jwt_in_request(optional=True)
            claims = get_jwt()
            if not claims:
                return response

            exp_ts = claims.get("exp")
            if not isinstance(exp_ts, (int, float)):
                return response

            now = datetime.now(timezone.utc)
            refresh_window = timedelta(
                minutes=int(app.config.get("JWT_REFRESH_WINDOW_MINUTES", 30))
            )
            if now + refresh_window < datetime.fromtimestamp(exp_ts, tz=timezone.utc):
                return response

            identity = get_jwt_identity()
            if identity is None:
                return response
            refreshed_token = create_access_token(identity=str(identity))
            set_access_cookies(response, refreshed_token)
        except Exception:
            # Best-effort refresh only.
            return response
        return response

    @app.after_request
    def add_response_headers(response):
        # CORS should be applied to both preflight and normal responses.
        response = _apply_cors_headers(response)

        # Set aggressive caching for content-hashed upload images.
        path = request.path
        # Only apply to /static/uploads/ paths with hash-like filenames
        if path.startswith('/static/uploads/') and '_' in path:
            # Filenames like 213_8fb5a09b46c0c5f8.png contain content hash
            # Safe to cache immutably
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        if _REQUEST_ID_HEADER not in response.headers:
            response.headers[_REQUEST_ID_HEADER] = getattr(
                g, "request_id", _resolve_request_id()
            )
        return response

    @app.after_request
    def log_request_response(response):
        request_id = getattr(g, "request_id", _resolve_request_id())
        route = _resolve_route()
        status = int(getattr(response, "status_code", 0) or 0)
        started_at = getattr(g, "request_started_at", None)
        if started_at is None:
            latency = 0.0
        else:
            latency = round((time.perf_counter() - started_at) * 1000, 2)
        error_code = _resolve_error_code_from_response(response)

        _log_request(
            request_logger,
            request_id=request_id,
            route=route,
            status=status,
            latency=latency,
            error_code=error_code,
        )
        g.request_logged = True
        response.headers[_REQUEST_ID_HEADER] = request_id
        return response

    @app.teardown_request
    def log_request_exception(exc):
        if exc is None or getattr(g, "request_logged", False):
            return None

        request_id = getattr(g, "request_id", _resolve_request_id())
        route = _resolve_route()
        started_at = getattr(g, "request_started_at", None)
        if started_at is None:
            latency = 0.0
        else:
            latency = round((time.perf_counter() - started_at) * 1000, 2)
        status = int(getattr(exc, "code", 500) or 500)
        error_code = getattr(exc, "name", None) or getattr(exc, "code", None)
        if error_code in (None, ""):
            error_code = "INTERNAL_SERVER_ERROR"
        _log_request(
            request_logger,
            request_id=request_id,
            route=route,
            status=status,
            latency=latency,
            error_code=str(error_code),
        )
        g.request_logged = True
        return None

    return app


def _register_full_blueprints(app: Flask) -> None:
    from app.routes.main import main_bp
    from app.routes.exam import exam_bp
    from app.routes.manage import manage_bp
    from app.routes.api_manage import api_manage_bp
    from app.routes.ai import ai_bp
    from app.routes.practice import practice_bp
    from app.routes.api_practice import api_practice_bp
    from app.routes.api_exam import api_exam_bp
    from app.routes.api_questions import api_questions_bp
    from app.routes.api_auth import api_auth_bp
    from app.routes.api_dashboard import api_dashboard_bp
    from app.routes.api_public_curriculum import api_public_curriculum_bp
    from app.routes.api_admin_curriculum import api_admin_curriculum_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(exam_bp, url_prefix="/exam")
    app.register_blueprint(manage_bp, url_prefix="/manage")
    app.register_blueprint(api_manage_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(practice_bp, url_prefix="/practice")
    app.register_blueprint(api_practice_bp, url_prefix="/api/practice")
    app.register_blueprint(api_exam_bp)
    app.register_blueprint(api_questions_bp)
    app.register_blueprint(api_auth_bp, url_prefix="/api/auth")
    app.register_blueprint(api_dashboard_bp)
    app.register_blueprint(api_public_curriculum_bp)
    app.register_blueprint(api_admin_curriculum_bp)


def _register_prototype_blueprints(app: Flask) -> None:
    from app.routes.main import main_bp

    app.register_blueprint(main_bp)
