"""메인 페이지 Blueprint"""
from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """대시보드 메인 페이지"""
    return render_template('index.html')
