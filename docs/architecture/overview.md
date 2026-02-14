# Architecture Overview

Exam Manager는 Next.js + Flask + PostgreSQL 조합의 분리형 구조를 사용합니다.

## Runtime Components

- Frontend: Next.js App Router (`next_app/src/app`)
- Backend: Flask 블루프린트 기반 API/Legacy UI (`app/routes`)
- Database: PostgreSQL only (`DATABASE_URL` 필수)
- Search/Index: `lecture_chunks` 기반 FTS + retrieval 파이프라인
- Optional AI: Gemini 기반 분류/텍스트 교정 (`/ai/*`)

## Request Flow

1. Browser -> Next.js (`http://localhost:4000`)
2. Next.js proxy (`/api/proxy/*`) -> Flask (`http://127.0.0.1:5000`)
3. Flask route/service -> PostgreSQL
4. 응답은 `ok/data` 포맷(신규) + 일부 legacy 포맷 병행

## Auth / Scope Model

- 인증: JWT(access token) + 쿠키(`auth_token`) 기반
- 인증 API: `app/routes/api_auth.py`
- 사용자 범위 제어: `app/services/user_scope.py`
  - 일반 사용자: 본인 데이터 중심
  - 관리자: 공개(public) + 사용자 데이터 접근 가능
- 일부 관리 라우트는 `LOCAL_ADMIN_ONLY` 설정으로 localhost 접근만 허용

## Core Backend Modules

- `app/routes/api_manage.py`: Subject/Block/Lecture/Exam/Question 관리 API
- `app/routes/api_exam.py`: 미분류 큐 API
- `app/routes/ai.py`: AI 분류 배치 + 진단 + 적용
- `app/routes/api_practice.py`: 연습/채점/세션/결과 API
- `app/routes/api_dashboard.py`: 대시보드/복습 지표 API
- `app/routes/api_public_curriculum.py`: 공개 템플릿 조회/복제
- `app/routes/api_admin_curriculum.py`: 공개 템플릿 관리자 API

## Data Model Highlights

- 커리큘럼: `Subject` -> `Block` -> `Lecture`
- 시험/문항: `PreviousExam` -> `Question` -> `Choice`
- 연습: `PracticeSession`, `PracticeAnswer`
- AI 분류: `ClassificationJob`, `QuestionChunkMatch`
- 공개 템플릿: `PublicCurriculumTemplate`

모델 정의는 `app/models.py`에 있습니다.

## Entry Points

- Local backend: `run.py`
- Production WSGI: `wsgi.py`
- Flask app factory: `app/__init__.py:create_app`
- Docker compose: `docker-compose.yml`
