"""Flask 애플리케이션 팩토리"""

import os
import re
from pathlib import Path

from flask import Flask, request
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy
from markupsafe import Markup, escape

from config import get_config, set_config_name
from config.base import DEFAULT_SECRET_KEY

# SQLAlchemy 인스턴스 (다른 모듈에서 import 가능)
db = SQLAlchemy()
jwt = JWTManager()
_MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


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

    # Set config profile name and load from new config package
    set_config_name(config_name)
    cfg = get_config()

    if config_name == "production":
        if not cfg.secret_key or cfg.secret_key == DEFAULT_SECRET_KEY:
            raise RuntimeError(
                "SECRET_KEY must be set to a non-default value in production."
            )
        if (
            not cfg.runtime.jwt_secret_key
            or cfg.runtime.jwt_secret_key == "dev-jwt-secret-key"
        ):
            raise RuntimeError(
                "JWT_SECRET_KEY must be set to a non-default value in production."
            )

    app.config["ENV_NAME"] = config_name
    app.config["SQLALCHEMY_DATABASE_URI"] = cfg.runtime.db_uri
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    if str(cfg.runtime.db_uri).startswith("postgres"):
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
    app.config["JWT_COOKIE_SECURE"] = config_name == "production"
    # HTML form posts in local/dev flows (e.g. manage delete actions) do not
    # send JWT CSRF headers. Keep strict CSRF in production only.
    app.config["JWT_COOKIE_CSRF_PROTECT"] = config_name == "production"
    app.config["LOCAL_ADMIN_ONLY"] = cfg.runtime.local_admin_only
    app.secret_key = cfg.secret_key
    app.config["UPLOAD_FOLDER"] = str(cfg.runtime.upload_folder)
    app.config["MAX_CONTENT_LENGTH"] = cfg.runtime.max_content_length
    app.config["APP_MODE"] = os.getenv("APP_MODE", "full")
    # Legacy routes still read parser mode from current_app.config.
    app.config["PDF_PARSER_MODE"] = cfg.experiment.pdf_parser_mode
    app.config["CORS_ALLOWED_ORIGINS"] = cfg.runtime.cors_allowed_origins
    app.config["CORS_ALLOW_CREDENTIALS"] = True

    # Legacy config mirror: get_config() is now the single source of truth.
    # Services migrated to use get_config() directly, no full mirror needed.
    # Legacy routes using current_app.config.get() will use default values.
    if db_uri_override:
        app.config["SQLALCHEMY_DATABASE_URI"] = db_uri_override

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
        from app.services.schema_patch import ensure_question_examiner_column

        ensure_question_examiner_column(app.logger)

    # 업로드 디렉토리 생성
    upload_folder = app.config.get("UPLOAD_FOLDER")
    if upload_folder and not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    # data 디렉토리 생성 (SQLite DB용)
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

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
    def handle_cors_preflight():
        if request.method == "OPTIONS":
            return _apply_cors_headers(app.make_default_options_response())
        return None

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
        return response

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
