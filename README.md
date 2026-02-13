# Exam Manager

Exam PDF parsing, classification, practice, and review web app.

## Recommended Run Modes
- Local development (fast iteration): Docker DB + local backend/frontend
- Docker full stack (deployment-like verification)

## Quick Start (Local Development)
1. Create env files
```bash
cp .env.example .env
cp .env.docker.example .env.docker
cp next_app/.env.local.example next_app/.env.local
```

2. Configure local DB connection in `.env` (if needed)
```bash
# optional override (when unset, scripts/dev-backend derives from .env.docker POSTGRES_* keys)
DATABASE_URL=postgresql+psycopg://exam:<POSTGRES_PASSWORD>@127.0.0.1:5432/exam_manager
```

3. Start DB container + initialize schema/FTS
```bash
./scripts/dev-db up -d db
./scripts/dev-init-db
```

4. Run backend/frontend in separate terminals
```bash
./scripts/dev-backend
./scripts/dev-frontend
```

5. Open
- Web: `http://localhost:4000`
- API health: `http://localhost:5000/health`

## Local Dev Commands
```bash
./scripts/dev-db ps
./scripts/dev-db logs -f db
./scripts/dev-db down
./scripts/dev-db down -v

# isolated dev DB (separate volume) when needed
DEV_DB_COMPOSE_FILE=docker-compose.local.yml ./scripts/dev-db up -d db
```

## Docker Full Stack (Production-like)
1. Create env file
```bash
cp .env.docker.example .env.docker
```

2. Set required secrets in `.env.docker`
- `SECRET_KEY`
- `JWT_SECRET_KEY`
- `POSTGRES_PASSWORD`

3. Start
```bash
./scripts/dc up -d --build
```

4. First-time initialization
```bash
./scripts/dc exec api sh -lc 'python scripts/init_db.py --config production --db "$DATABASE_URL"'
./scripts/dc exec api sh -lc 'python scripts/init_fts.py --db "$DATABASE_URL" --sync'
./scripts/dc exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"'
```

5. Common commands
```bash
./scripts/dc up -d
./scripts/dc down
./scripts/dc ps
./scripts/dc logs -f api web
```

## After Deploying PDF Crop Fixes
If you updated parser/crop logic, run these in Docker once:
```bash
# rebuild + restart api
./scripts/dc up -d --build api

# backfill existing question.image_path to exam_crops paths
./scripts/dc exec api sh -lc 'python scripts/backfill_crop_image_paths.py --config production --apply'
```

## Local PDF Lab (Backend-only)
빠른 파서 실험 루프:
```bash
.venv/bin/python scripts/pdf_lab.py --pdf parse_lab/pdfs/sample.pdf --mode experimental --watch
```

산출물은 `parse_lab/output/lab_runs/` 아래에 run별로 저장됩니다.

## Run Tests
```bash
# Postgres test run (recommended, auto-creates *_test DB if needed)
./scripts/dev-test-backend

# Optional: explicit URI
TEST_DATABASE_URL=postgresql+psycopg://exam:<POSTGRES_PASSWORD>@127.0.0.1:5432/exam_manager_test \
PYTHONPATH=. ./.venv/bin/pytest -q
```

## Legacy: one-time Historical Import (Optional)
Postgres is the only supported runtime DB.  
If you still have old file-based data, run the one-time legacy import utility under `scripts/legacy/`, then resync FTS:
```bash
./scripts/dc exec -T api sh -lc 'python scripts/init_fts.py --db "$DATABASE_URL" --sync'
```

## Project Layout
- `app/`: Flask backend
- `next_app/`: Next.js frontend
- `docker/`: Dockerfiles
- `scripts/`: operation and migration scripts
- `docs/`: setup and architecture docs
- `migrations/`: schema migration SQL

## Docs
- `docs/README.md`
- `docs/setup/local-dev.md`
- `docs/setup/docker.md`
- `docs/setup/env.md`
- `docs/architecture/overview.md`
