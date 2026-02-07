# Docker Run Guide

Docker is the primary run mode.

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
./scripts/dc exec api sh -lc 'python scripts/init_fts.py --db "$DATABASE_URL" --sync'
./scripts/dc exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"'
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

## 6) Dev compose (optional)
```bash
docker compose --env-file .env.docker -f docker-compose.dev.yml up --build
```
