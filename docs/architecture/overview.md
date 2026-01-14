# 아키텍처 개요

## 한눈에 보기
- Flask: 레거시 관리 UI + JSON API + PDF/AI 처리
- Next.js: 관리/연습 UI (서버에서 Flask API 호출)
- SQLite: 단일 파일 DB (`data/exam.db`, `data/admin_local.db`)
- 업로드 자산: `app/static/uploads` (local admin은 `uploads_admin`)

## 주요 구성 요소
- `app/routes/`: Flask Blueprint (manage/exam/practice/ai/api)
- `app/services/`: PDF 파싱, AI 분류, 강의 노트 인덱싱 등 비즈니스 로직
- `app/models.py`: SQLAlchemy 모델 정의 (스키마 단일 기준)
- `app/templates/`: Flask 레거시 UI
- `next_app/`: Next.js App Router UI
- `next_app/src/app/api/proxy/`: Next.js → Flask 프록시

## 요청 흐름 (예시)
### 1) PDF 업로드
- Next.js `/manage/upload-pdf` → `/api/manage/upload-pdf`
- Flask에서 PDF 파싱 → `previous_exams`, `questions` 저장 + 이미지 파일 생성

### 2) 문제 분류
- 레거시 UI 또는 Next.js에서 분류 요청
- Flask에서 `Question.lecture_id` 업데이트

### 3) AI 분류
- `/exam/unclassified`에서 배치 시작 → 백그라운드 스레드로 Gemini 호출
- `classification_jobs` 상태 업데이트

### 4) 강의 노트 인덱싱 (FTS)
- 레거시 `/manage/lecture/<id>`에서 PDF 업로드
- `lecture_chunks` 생성 → FTS 테이블(`lecture_chunks_fts`)은 `scripts/init_fts.py`로 초기화

### 5) 연습 흐름
- Next.js `/lectures` → `/api/practice/lectures`
- `/practice/start`에서 문제 로딩: `/api/practice/lecture/<id>/questions`
- 제출: `/api/practice/lecture/<id>/submit`
- 결과: `/api/practice/lecture/<id>/result`
- 세션 생성은 클라이언트 fallback 방식이며, 서버 세션은 제출 시 저장됨
- 레거시 연습 UI는 서버 렌더링 흐름을 유지

## Local admin
- `run_local_admin.py`는 `LocalAdminConfig`를 사용
- DB: `data/admin_local.db`
- PDF 파서: `experimental` 고정
- `/manage` 접근은 localhost로 제한

## 제약/주의
- `LOCAL_ADMIN_ONLY`가 활성화되면 `/manage` 및 관련 API 접근이 localhost로 제한됩니다.
- `PDF_PARSER_MODE` 값에 따라 파서가 `legacy`/`experimental` 중 선택됩니다.
- 스키마 변경은 `app/models.py` + 마이그레이션 스크립트 동시 업데이트가 필요합니다.
- `scripts/*`는 기본 설정(`data/exam.db`)을 기준으로 동작합니다.
