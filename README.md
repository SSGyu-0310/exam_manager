# Exam Manager

기출 시험 PDF를 파싱해 문제를 저장하고, 블록/강의 단위로 분류하며, 연습/채점/복습까지 연결하는 학습 관리 앱입니다.

## Stack
- Backend: Flask + SQLAlchemy + JWT Cookie Auth
- Frontend: Next.js(App Router) + React + Tailwind
- Database: SQLite(기존) / Postgres(배포 권장)
- AI: Gemini (`GEMINI_API_KEY` 설정 시 사용)

## Quick Start (Docker 권장)
1. 환경파일 생성
```bash
cp .env.docker.example .env.docker
```
2. 시크릿 수정
- `SECRET_KEY`
- `JWT_SECRET_KEY`
- `POSTGRES_PASSWORD`

3. 배포 기준 환경 실행
```bash
docker compose --env-file .env.docker up -d --build
```

4. 초기화(최초 1회)
```bash
docker compose --env-file .env.docker exec api sh -lc 'python scripts/init_db.py --config production --db "$DATABASE_URL"'
docker compose --env-file .env.docker exec api sh -lc 'python scripts/init_fts.py --db "$DATABASE_URL" --sync'
docker compose --env-file .env.docker exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"'
```

5. 접속
- Web: `http://localhost:4000`
- API health: `http://localhost:5000/health`

상세: `docs/setup/docker.md`

## Local Dev (Non-Docker)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd next_app
npm install
cd ..

cp .env.example .env
cat > next_app/.env.local <<'EOT'
FLASK_BASE_URL=http://127.0.0.1:5000
EOT

python scripts/init_db.py --db data/exam.db
python scripts/init_fts.py --db data/exam.db --sync
python scripts/dev.py
```

## SQLite -> Postgres Migration
```bash
docker cp data/exam.db exam_manager-api-1:/tmp/exam.db
docker compose --env-file .env.docker exec -T api sh -lc 'python scripts/migrate_sqlite_to_postgres.py --sqlite /tmp/exam.db --postgres "$DATABASE_URL"'
docker compose --env-file .env.docker exec -T api sh -lc 'python scripts/init_fts.py --db "$DATABASE_URL" --sync'
```

## Directory Layout
- `app/`: Flask routes/services/models/templates
- `next_app/`: Next.js frontend
- `config/`: runtime/experiment config
- `scripts/`: 운영/마이그레이션 스크립트
- `migrations/`: SQL migration files
- `docs/`: setup/architecture/ops docs
- `data/`: 로컬 DB 및 캐시(로컬 전용)

## Documentation Index
- `docs/README.md`
- `docs/setup/docker.md`
- `docs/setup/env.md`
- `docs/architecture/overview.md`
- `docs/operations/scripts.md`

## Notes
- `.env`, `.env.docker`, DB 파일, 캐시/리포트는 Git 추적 대상이 아닙니다.
- 프로덕션에서는 `FLASK_CONFIG=production`과 강한 시크릿 키를 반드시 사용하세요.
