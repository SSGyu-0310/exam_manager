# WSL Setup (Docker)

WSL usage is Docker-first.

## Prerequisites
- Docker Desktop installed on Windows
- WSL2 integration enabled for your distro

## Run
```bash
cd /home/gyu/learn/exam_manager
cp .env.docker.example .env.docker
# edit .env.docker secrets
./scripts/dc up -d --build
```

## First-time init
```bash
./scripts/dc exec api sh -lc 'python scripts/init_db.py --config production --db "$DATABASE_URL"'
./scripts/dc exec api sh -lc 'python scripts/init_fts.py --db "$DATABASE_URL" --sync'
./scripts/dc exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"'
```

## Access
- `http://localhost:4000`
- `http://localhost:5000/health`

## Stop
```bash
./scripts/dc down
```
