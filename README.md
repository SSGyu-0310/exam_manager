# Exam Manager

Exam PDF parsing, classification, practice, and review web app.

## Recommended Run Mode
Docker Compose is the single supported run path.

## Quick Start
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

5. Open
- Web: `http://localhost:4000`
- API health: `http://localhost:5000/health`

## Common Commands
```bash
./scripts/dc up -d
./scripts/dc down
./scripts/dc ps
./scripts/dc logs -f api web
```

## SQLite to Postgres Migration
```bash
docker cp data/exam.db exam_manager-api-1:/tmp/exam.db
./scripts/dc exec -T api sh -lc 'python scripts/migrate_sqlite_to_postgres.py --sqlite /tmp/exam.db --postgres "$DATABASE_URL"'
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
- `docs/setup/docker.md`
- `docs/setup/env.md`
- `docs/architecture/overview.md`
