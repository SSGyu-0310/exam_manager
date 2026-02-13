# Local Development Guide

Recommended workflow for fast backend/frontend iteration:
- Postgres in Docker
- Flask + Next.js on host (hot reload)

## 1) Prepare env files
```bash
cp .env.example .env
cp .env.docker.example .env.docker
cp next_app/.env.local.example next_app/.env.local
```

Set/verify in `.env`:
```dotenv
FLASK_CONFIG=development
FLASK_DEBUG=1
# Optional override. If unset, scripts/dev-backend uses .env.docker POSTGRES_*.
DATABASE_URL=postgresql+psycopg://exam:<POSTGRES_PASSWORD>@127.0.0.1:5432/exam_manager
SEARCH_BACKEND=postgres
CORS_ALLOWED_ORIGINS=http://localhost:4000
# Optional pytest DB name override (default: ${POSTGRES_DB}_test)
# POSTGRES_TEST_DB=exam_manager_test
```

## 2) Start local DB container
```bash
./scripts/dev-db up -d db
```

## 3) One-time DB initialization
```bash
./scripts/dev-init-db
```

`./scripts/dev-init-db` now also runs `scripts/run_postgres_migrations.py`, which applies
`migrations/postgres/*.sql` and records checksums in `schema_migrations`.

## 4) Run backend and frontend
Terminal 1:
```bash
./scripts/dev-backend
```

Terminal 2:
```bash
./scripts/dev-frontend
```

## 5) Access
- Web: `http://localhost:4000`
- API health: `http://localhost:5000/health`

## 6) Run backend tests (Postgres)
```bash
./scripts/dev-test-backend
```

## Local Dev Commands
```bash
# DB lifecycle
./scripts/dev-db ps
./scripts/dev-db logs -f db
./scripts/dev-db down
./scripts/dev-db down -v

# Re-run DB initialization after reset
./scripts/dev-init-db

# Backend tests on Postgres test DB
./scripts/dev-test-backend
```

## Notes
- `scripts/dev-db` uses the same compose DB as `./scripts/dc` by default, so existing Docker data is reused.
- `scripts/dev-db` adds host port mapping (`127.0.0.1:5432`) via `docker-compose.host-db.yml`.
- `scripts/dev-backend` and `scripts/dev-init-db` load `.env.docker` first, then `.env` overrides.
- `scripts/dev-backend` auto-starts/waits for DB by default (`DEV_BACKEND_AUTO_START_DB=1`).
- `scripts/dev-frontend` auto-creates `next_app/.env.local` if missing.
- If you want isolated local DB volume, run with `DEV_DB_COMPOSE_FILE=docker-compose.local.yml`.
- Use `./scripts/dc up -d --build` when you need full Docker verification before deploy.
