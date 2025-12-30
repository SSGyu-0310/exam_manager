"""애플리케이션 엔트리포인트"""
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

from app import create_app

# 앱 인스턴스 생성
app = create_app(os.environ.get('FLASK_CONFIG') or 'default')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
