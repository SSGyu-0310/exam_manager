"""Flask 애플리케이션 팩토리"""
import os
import re
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from markupsafe import Markup, escape

from config import config

# SQLAlchemy 인스턴스 (다른 모듈에서 import 가능)
db = SQLAlchemy()
_MARKDOWN_IMAGE_PATTERN = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')


def render_markdown_images(value):
    """Render markdown image syntax to HTML img tags, escaping other text."""
    if value is None:
        return ''
    text = str(value)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    parts = []
    last_index = 0
    for match in _MARKDOWN_IMAGE_PATTERN.finditer(text):
        parts.append(escape(text[last_index:match.start()]))
        alt_text = escape(match.group(1))
        url = escape(match.group(2).strip())
        parts.append(f'<img src="{url}" alt="{alt_text}" class="markdown-image">')
        last_index = match.end()
    parts.append(escape(text[last_index:]))
    return Markup(''.join(parts))


def create_app(config_name='default'):
    """
    Flask 애플리케이션 팩토리
    
    Args:
        config_name: 설정 이름 ('development', 'production', 'default')
    
    Returns:
        Flask 앱 인스턴스
    """
    app = Flask(__name__)
    
    # 설정 로드
    app.config.from_object(config[config_name])
    
    # SQLAlchemy 초기화
    db.init_app(app)
    
    # 업로드 디렉토리 생성
    upload_folder = app.config.get('UPLOAD_FOLDER')
    if upload_folder and not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    
    # data 디렉토리 생성 (SQLite DB용)
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    
    # Blueprint 등록
    from app.routes.main import main_bp
    from app.routes.exam import exam_bp
    from app.routes.manage import manage_bp
    from app.routes.api_manage import api_manage_bp
    from app.routes.ai import ai_bp
    from app.routes.practice import practice_bp
    from app.routes.api_practice import api_practice_bp
    from app.routes.api_exam import api_exam_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(exam_bp, url_prefix='/exam')
    app.register_blueprint(manage_bp, url_prefix='/manage')
    app.register_blueprint(api_manage_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(practice_bp, url_prefix='/practice')
    app.register_blueprint(api_practice_bp, url_prefix='/api/practice')
    app.register_blueprint(api_exam_bp)

    app.jinja_env.filters['md_image'] = render_markdown_images
    
    # 앱 컨텍스트에서 DB 테이블 생성
    if app.config.get('AUTO_CREATE_DB'):
        with app.app_context():
            db.create_all()
    
    return app
