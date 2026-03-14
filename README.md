# Exam Manager

Exam Manager는 시험지 PDF를 업로드해 문항을 생성하고, 강의 체계에 분류한 뒤,
연습/복습까지 연결하는 학습 관리 웹 애플리케이션입니다.

- Backend: Flask + SQLAlchemy
- Frontend: Next.js (App Router)
- Database: PostgreSQL (runtime Postgres-only)

## 요구사항

- Python 3.10+
- Node.js + npm
- Docker + Docker Compose (권장 개발/운영 워크플로)

## 빠른 시작 (로컬 개발)

권장: DB는 Docker, 백엔드/프론트는 호스트에서 실행

공통 런타임 기준은 [docs/setup/runtime-policy.md](docs/setup/runtime-policy.md)를 따릅니다.

1. 환경 파일 생성

```bash
cp .env.example .env
cp .env.docker.example .env.docker
cp next_app/.env.local.example next_app/.env.local
```

2. 의존성 설치

```bash
python -m pip install -r requirements.txt
cd next_app && npm install
```

3. 원클릭 실행 (DB + 백엔드 + 프론트)

```bash
./scripts/dev-stack up --init-db
```

4. 접속

- Web: `http://localhost:4000`
- API health: `http://localhost:${API_PORT:-5000}/health`

5. 최초 계정 생성

- `http://localhost:4000/register`

분리 실행이 필요하면:

```bash
./scripts/dev-db up -d db
./scripts/dev-init-db
./scripts/dev-backend
./scripts/dev-frontend
```

분리 실행 종료:

```bash
./scripts/dev-db down
```

`./scripts/dev-backend`, `./scripts/dev-frontend`는 각 터미널에서 `Ctrl+C`

원클릭 실행 종료:

```bash
./scripts/dev-stack down
```

## Docker 전체 스택 실행

배포 전 검증용 Docker 실행 기준도 [docs/setup/runtime-policy.md](docs/setup/runtime-policy.md)에 정리돼 있습니다.

1. `.env.docker` 생성

```bash
cp .env.docker.example .env.docker
```

2. 필수 값 설정

- `SECRET_KEY`
- `JWT_SECRET_KEY`
- `POSTGRES_PASSWORD`

3. 컨테이너 실행

```bash
./scripts/dc up -d --build
```

4. 최초 초기화

```bash
./scripts/dc exec api sh -lc 'python scripts/init_db.py --config production --db "$DATABASE_URL"'
./scripts/dc exec api sh -lc 'python scripts/run_postgres_migrations.py --db "$DATABASE_URL"'
./scripts/dc exec api sh -lc 'python scripts/init_fts.py --db "$DATABASE_URL" --sync'
./scripts/dc exec api sh -lc 'python scripts/migrate_ai_fields.py --config production --db "$DATABASE_URL"'
./scripts/dc exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"'
./scripts/dc exec api sh -lc 'python scripts/verify_postgres_setup.py --db "$DATABASE_URL"'
```

## 환경 변수 요약

- 로컬 백엔드 스크립트(`dev-backend`, `dev-init-db`, `dev-test-backend`) 로딩 순서:
  1) `.env.docker` 2) `.env` (동일 키는 `.env`가 override)
- Docker compose(`scripts/dc`, `scripts/dev-db`): 기본 `.env.docker`
- 프론트엔드(`scripts/dev-frontend`): `next_app/.env.local`

주요 필수 키:
- `DATABASE_URL`
- `FLASK_CONFIG`
- `SECRET_KEY`
- `JWT_SECRET_KEY`
- `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB`

## 테스트

기본:

```bash
./scripts/dev-test-backend
```

직접 실행:

```bash
TEST_DATABASE_URL=postgresql+psycopg://exam:<POSTGRES_PASSWORD>@127.0.0.1:5432/exam_manager_test \
PYTHONPATH=. python -m pytest -q
```

## 현재 기능 스냅샷

- 인증: 회원가입/로그인/로그아웃, JWT 쿠키 인증
- 커리큘럼 관리: Subject/Block/Lecture CRUD, 공개/개인 스코프
- 강의 자료 인덱싱: 강의노트 PDF 업로드 및 청크 인덱싱
- 시험/문항 관리: 시험 CRUD, PDF 파싱, 문항/선지 편집
- 미분류 큐/분류: 조회/필터/일괄 처리 + AI 분류 배치(시작/상태/결과/적용/진단)
- 연습/채점: 강의/시험 기반 풀이, 제출, 결과/세션 조회
- 학습 이어하기: 미완료 세션 자동 탐색 후 `이어하기/새로 시작` 분기 지원
- 대시보드/복습: 진행도, 약점 분석, 노트, 이력
- 복습 동선: 노트/북마크에서 해당 강의 세션으로 진입 후 `questionId` 기반 문항 점프 지원
- 공개 템플릿: 조회/복제 + 관리자 템플릿 관리
- Legacy UI: Flask 템플릿 화면과 Next 화면 병행 운영

현재 Partial:
- `/learn/recommended`는 화면 중심(추천 엔진 미완성)
- Next 세션 시작 API는 일부 경로에서 fallback(sessionStorage) 사용

## 자주 쓰는 명령

```bash
# one-command stack
./scripts/dev-stack up
./scripts/dev-stack status
./scripts/dev-stack logs all
./scripts/dev-stack down

# DB lifecycle
./scripts/dev-db ps
./scripts/dev-db logs -f db
./scripts/dev-db down
./scripts/dev-db down -v

# Docker stack
./scripts/dc up -d --build
./scripts/dc logs -f api web
./scripts/dc down
```

## 문서

- 문서 인덱스: `docs/README.md`
- 로컬 개발: `docs/setup/local-dev.md`
- Docker 가이드: `docs/setup/docker.md`
- 환경 변수: `docs/setup/env.md`
- 기능 스냅샷: `docs/features.md`
- 아키텍처 개요: `docs/architecture/overview.md`
- 라우트/기능 매핑: `docs/architecture/map.md`
- API 가이드: `docs/api.md`
- API(개발): `docs/api-dev.md`
- API(운영): `docs/api-ops.md`

## 디렉터리 구조

- `app/`: Flask 백엔드
- `next_app/`: Next.js 프론트엔드
- `scripts/`: 개발/운영 스크립트
- `migrations/`: SQL 마이그레이션
- `docs/`: 프로젝트 문서
