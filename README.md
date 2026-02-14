# Exam Manager

Exam Manager는 시험지 PDF를 업로드해 문제를 생성하고, 강의 체계에 분류하고,
연습/복습까지 이어지는 학습 워크플로를 제공하는 웹 애플리케이션입니다.

- Backend: Flask + SQLAlchemy
- Frontend: Next.js (App Router)
- Database: PostgreSQL (runtime은 Postgres-only)

## 현재 구현된 기능

### 콘텐츠 관리
- 과목(Subject) / 블록(Block) / 강의(Lecture) 관리
- 시험지(Exam) 관리 및 PDF 업로드 기반 문제 생성
- 문제/선지 수정, 이미지 업로드, 강의노트 PDF 인덱싱

### 분류
- 미분류 큐 조회/검색/필터
- 수동 분류, 일괄 분류/이동/초기화
- AI 분류 배치 작업(시작/상태/결과/적용/진단)

### 학습/복습
- 강의 기반 연습(객관식/복수정답/주관식)
- 시험 기반 연습 결과 조회
- 세션 히스토리, 약점 분석, 복습 노트/이력 대시보드

### 인증/공개 템플릿
- 회원가입/로그인/로그아웃/JWT 쿠키 인증
- 공개 커리큘럼 템플릿 조회/복제

### 현재 제한사항
- Next 기준 세션 생성 API는 일부 경로에서 fallback(sessionStorage) 동작을 사용합니다.
- `/learn/recommended` 등 일부 화면은 안내용(준비 중)입니다.
- Legacy Flask 템플릿 화면과 Next 화면이 병행 운영 중입니다.

## 빠른 시작 (로컬 개발)

1) 환경 파일 생성

```bash
cp .env.example .env
cp .env.docker.example .env.docker
cp next_app/.env.local.example next_app/.env.local
```

2) 의존성 설치

```bash
python -m pip install -r requirements.txt
cd next_app && npm install
```

3) DB 컨테이너 기동 + 스키마/FTS 초기화

```bash
./scripts/dev-db up -d db
./scripts/dev-init-db
```

4) 백엔드/프론트엔드 실행 (각각 별도 터미널)

```bash
./scripts/dev-backend
./scripts/dev-frontend
```

5) 접속

- Web: `http://localhost:4000`
- API health: `http://localhost:5000/health`

6) 최초 계정 생성

- `http://localhost:4000/register` 에서 계정을 만든 뒤 로그인합니다.

## Docker 전체 스택 실행

1) `.env.docker` 준비

```bash
cp .env.docker.example .env.docker
```

2) 필수 값 설정

- `SECRET_KEY`
- `JWT_SECRET_KEY`
- `POSTGRES_PASSWORD`

3) 컨테이너 실행

```bash
./scripts/dc up -d --build
```

4) 초기화

```bash
./scripts/dc exec api sh -lc 'python scripts/init_db.py --config production --db "$DATABASE_URL"'
./scripts/dc exec api sh -lc 'python scripts/run_postgres_migrations.py --db "$DATABASE_URL"'
./scripts/dc exec api sh -lc 'python scripts/init_fts.py --db "$DATABASE_URL" --sync'
./scripts/dc exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"'
```

## 테스트

```bash
./scripts/dev-test-backend
```

필요 시 직접 실행:

```bash
TEST_DATABASE_URL=postgresql+psycopg://exam:<POSTGRES_PASSWORD>@127.0.0.1:5432/exam_manager_test \
PYTHONPATH=. python -m pytest -q
```

## 자주 쓰는 명령

```bash
# DB 상태
./scripts/dev-db ps
./scripts/dev-db logs -f db

# 종료/정리
./scripts/dev-db down
./scripts/dev-db down -v

# 도커 스택 로그
./scripts/dc logs -f api web
```

## 문서

- 문서 인덱스: `docs/README.md`
- 기능 기준 정리: `docs/features.md`
- 아키텍처 개요: `docs/architecture/overview.md`
- 라우트/기능 매핑: `docs/architecture/map.md`
- API 가이드: `docs/api.md`
- API(개발): `docs/api-dev.md`
- API(운영): `docs/api-ops.md`

## 디렉터리 구조

- `app/`: Flask 백엔드
- `next_app/`: Next.js 프론트엔드
- `scripts/`: 운영/개발 스크립트
- `migrations/`: SQL 마이그레이션
- `docs/`: 프로젝트 문서
