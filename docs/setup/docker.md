# Docker 기반 실행 가이드

이 문서는 **배포 기준 환경(Postgres + Gunicorn + Next.js start)** 과
**개발 지속 환경(핫리로드)** 을 분리해 실행하는 방법을 설명합니다.

## 1) 파일 개요

- `docker-compose.yml`: 배포 기준 환경
- `docker-compose.dev.yml`: 개발 지속 환경
- `docker/backend.Dockerfile`: Flask/Gunicorn 이미지
- `docker/frontend.Dockerfile`: Next.js(dev/build/start) 이미지
- `.env.docker.example`: Docker용 환경변수 예시

## 2) 사전 준비

```bash
cp .env.docker.example .env.docker
```

- `SECRET_KEY`, `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`를 반드시 변경하세요.
- AI 기능을 쓰면 `GEMINI_API_KEY`를 추가하세요.

## 3) 배포 기준 환경 실행

```bash
docker compose --env-file .env.docker up -d --build
```

초기 1회 스키마/FTS 준비:

```bash
docker compose --env-file .env.docker exec api sh -lc 'python scripts/init_db.py --config production --db "$DATABASE_URL"'
docker compose --env-file .env.docker exec api sh -lc 'python scripts/init_fts.py --db "$DATABASE_URL" --sync'
docker compose --env-file .env.docker exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"'
```

헬스체크:

```bash
curl http://localhost:5000/health
curl http://localhost:4000
```

## 4) 개발 지속 환경 실행

```bash
docker compose --env-file .env.docker -f docker-compose.dev.yml up --build
```

- 백엔드: 코드 변경 시 자동 재시작 (`FLASK_DEBUG=1`, `python run.py`)
- 프론트: `next dev` 핫리로드
- DB: Postgres 로컬 포트 `5432` 노출

초기화(개발 DB 1회):

```bash
docker compose --env-file .env.docker -f docker-compose.dev.yml exec api sh -lc 'python scripts/init_db.py --config development --db "$DATABASE_URL"'
docker compose --env-file .env.docker -f docker-compose.dev.yml exec api sh -lc 'python scripts/init_fts.py --db "$DATABASE_URL" --sync'
```

## 5) 운영 전 체크 포인트

1. `SECRET_KEY`, `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`를 강한 값으로 변경
2. `CORS_ALLOWED_ORIGINS`를 실제 도메인으로 고정
3. `NEXT_PUBLIC_SITE_URL`/`NEXT_PUBLIC_APP_URL`를 실제 도메인으로 고정
4. Postgres 백업 정책(스냅샷/PITR) 설정
5. 에러 로깅/모니터링(Sentry 등) 연결

## 6) 로드맵 (권장)

### Phase 1 (오늘)
- Docker 배포 기준 환경 기동
- DB 초기화 + FTS 동기화
- 기본 기능(로그인/문항조회/업로드) smoke test

### Phase 2 (이번 주)
- SQLite 데이터 Postgres 이관 (`scripts/migrate_sqlite_to_postgres.py`)
- Postgres 인덱스 적용 (`scripts/apply_postgres_indexes.py`)
- 검증 (`scripts/verify_postgres_setup.py`)

### Phase 3 (다음 주)
- CI에서 이미지 빌드/취약점 스캔
- 배포 자동화(태그 기반)
- 모니터링/알람/백업 복구 리허설

## 7) 자주 쓰는 명령

```bash
# 종료
docker compose --env-file .env.docker down
docker compose --env-file .env.docker -f docker-compose.dev.yml down

# 로그
docker compose --env-file .env.docker logs -f api web
docker compose --env-file .env.docker -f docker-compose.dev.yml logs -f api web

# DB 접속
docker compose --env-file .env.docker exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```
