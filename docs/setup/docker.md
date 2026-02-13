# Docker Run Guide

Docker full stack is recommended for deployment-like verification.
For fast coding iteration, see `docs/setup/local-dev.md`.

## 1) Prepare
```bash
cp .env.docker.example .env.docker
# edit secrets in .env.docker
```

Required secrets:
- `SECRET_KEY`
- `JWT_SECRET_KEY`
- `POSTGRES_PASSWORD`

## 2) Start
Preferred (short):
```bash
./scripts/dc up -d --build
```

Equivalent long command:
```bash
docker compose --env-file .env.docker up -d --build
```

## 3) First-time init
```bash
./scripts/dc exec api sh -lc 'python scripts/init_db.py --config production --db "$DATABASE_URL"'
./scripts/dc exec api sh -lc 'python scripts/run_postgres_migrations.py --db "$DATABASE_URL"'
./scripts/dc exec api sh -lc 'python scripts/init_fts.py --db "$DATABASE_URL" --sync'
./scripts/dc exec api sh -lc 'python scripts/migrate_ai_fields.py --config production --db "$DATABASE_URL"'
./scripts/dc exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"'
./scripts/dc exec api sh -lc 'python scripts/verify_postgres_setup.py --db "$DATABASE_URL"'
```

## 4) Access
- Web: `http://localhost:4000`
- API health: `http://localhost:5000/health`

## 5) Common commands
```bash
./scripts/dc up -d
./scripts/dc down
./scripts/dc ps
./scripts/dc logs -f api web
./scripts/dc exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

## 6) Local dev alternative (faster edit loop)
```bash
./scripts/dev-db up -d db
./scripts/dev-backend   # terminal 1
./scripts/dev-frontend  # terminal 2
```

## 7) AI 분류 진단 (원인 추적)
1. 실시간 분류 로그 보기
```bash
./scripts/dc logs -f api | rg "CLASSIFIER_"
```

2. 특정 job 진단 JSON 조회 (HTTP)
```bash
curl -s "http://localhost:5000/ai/classify/diagnostics/<JOB_ID>?include_rows=1&row_limit=100"
```

3. 특정 job 진단 출력 (컨테이너 내부 스크립트)
```bash
./scripts/dc exec api sh -lc 'python scripts/inspect_classification_job.py --job-id <JOB_ID> --config production'
```

4. 디버그 로그 활성화 (선택)
- `.env.docker`에 `CLASSIFIER_DEBUG_LOG=1` 추가 후 `./scripts/dc up -d --build` 재기동
