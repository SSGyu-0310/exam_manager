# Configuration Reference

현재 프로젝트의 설정은 `config/` 패키지와 환경 변수로 구성됩니다.

## Source of Truth

- 템플릿 파일
  - `.env.example`
  - `.env.docker.example`
  - `next_app/.env.local.example`
- 런타임 설정 코드
  - `config/runtime.py`
  - `config/experiment.py`
  - `config/base.py`

## 환경 파일 로딩 우선순위

### 백엔드 로컬 스크립트 (`dev-backend`, `dev-init-db`, `dev-test-backend`)

1. `.env.docker`
2. `.env` (같은 키는 `.env`가 override)

### Docker compose (`scripts/dc`, `scripts/dev-db`)

- 기본 `ENV_FILE=.env.docker`

### Next.js (`scripts/dev-frontend`)

- `next_app/.env.local`

## 필수 키

### Local Dev

| Key | 설명 |
| --- | --- |
| `DATABASE_URL` | Postgres 연결 문자열 (`postgresql+psycopg://...`) |
| `FLASK_CONFIG` | 보통 `development` |

### Docker / Production-like

| Key | 설명 |
| --- | --- |
| `DATABASE_URL` | API 컨테이너 DB 연결 |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | DB 컨테이너 초기값 |
| `SECRET_KEY` | Flask 시크릿 |
| `JWT_SECRET_KEY` | JWT 서명 시크릿 |

## Core Runtime Keys

| Key | 기본값 | 설명 |
| --- | --- | --- |
| `DATABASE_URL` | 없음(필수) | Postgres URI |
| `FLASK_CONFIG` | `development` | `development` / `production` / `local_admin` |
| `JWT_COOKIE_SECURE` | prod: `1`, dev: `0` | HTTPS 전용 쿠키 여부 |
| `JWT_ACCESS_TOKEN_EXPIRES_MINUTES` | `720` | 액세스 토큰 만료(분) |
| `JWT_REFRESH_WINDOW_MINUTES` | `30` | 만료 임박 시 재발급 윈도우(분) |
| `LOCAL_ADMIN_ONLY` | `0` | localhost 전용 접근 제한 |
| `DB_READ_ONLY` | `0` | 쓰기 금지 모드 |
| `CHECK_PENDING_MIGRATIONS` | `1` | 앱 시작 시 migration 검사 |
| `FAIL_ON_PENDING_MIGRATIONS` | `0` | 미적용 migration 발견 시 실패 |
| `MAX_CONTENT_LENGTH` | `104857600` | 요청 본문 최대 크기(바이트) |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:4000` | 허용 Origin 목록 |

## AI / Retrieval 주요 키

| Key | 설명 |
| --- | --- |
| `GEMINI_API_KEY` | AI 분류/교정 기능 활성화 |
| `GEMINI_MODEL_NAME` | Gemini 모델 지정 |
| `AI_AUTO_APPLY` | AI 결과 자동 적용 여부 |
| `RETRIEVAL_MODE` | retrieval 모드 (`bm25`) |
| `SEARCH_BACKEND` | 검색 백엔드 (`auto`, `postgres`) |
| `SEARCH_PG_QUERY_MODE` | tsquery 모드 (`websearch`, `plainto`, `to_tsquery`) |
| `CLASSIFIER_REJUDGE_*` | no-match 재판단 파라미터 |
| `CLASSIFIER_DEBUG_LOG` | 분류 디버그 로그 출력 여부 |

## PDF / Upload 관련 키

| Key | 설명 |
| --- | --- |
| `PDF_PARSER_MODE` | `legacy` / `experimental` |
| `KEEP_PDF_AFTER_INDEX` | 인덱싱 후 원본 PDF 유지 여부 |
| `UPLOAD_FOLDER` | 업로드 저장 경로 (미설정 시 `app/static/uploads`) |

## Next.js 관련 키

| Key | 설명 |
| --- | --- |
| `FLASK_BASE_URL` | Next proxy가 호출할 Flask base URL |
| `NEXT_PUBLIC_SITE_URL` | 서버 사이드 fetch base URL |
| `NEXT_PUBLIC_APP_URL` | `SITE_URL` 대체 fallback |

## 운영 권장

- `.env`, `.env.docker`, `next_app/.env.local`은 git에 커밋하지 않습니다.
- 설정 변경 후 프로세스를 재시작합니다.
  - 로컬: 백엔드/프론트 재시작
  - 도커: `./scripts/dc up -d --build`
