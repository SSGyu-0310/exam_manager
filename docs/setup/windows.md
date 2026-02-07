# Windows Setup (Docker)

Windows execution is Docker-first.

## Prerequisites
- Docker Desktop installed
- `docker compose` available in terminal

## Run (PowerShell)
```powershell
cd C:\path\to\exam_manager
copy .env.docker.example .env.docker
# edit secrets in .env.docker
docker compose --env-file .env.docker up -d --build
```

## First-time init
```powershell
docker compose --env-file .env.docker exec api sh -lc 'python scripts/init_db.py --config production --db "$DATABASE_URL"'
docker compose --env-file .env.docker exec api sh -lc 'python scripts/init_fts.py --db "$DATABASE_URL" --sync'
docker compose --env-file .env.docker exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"'
```

## Access
- `http://localhost:4000`
- `http://localhost:5000/health`
