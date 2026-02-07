# Architecture Overview

Exam Manager uses a split frontend/backend architecture.

## Components
- Frontend: Next.js App Router (`next_app/src/app`)
- Backend: Flask API + legacy templates (`app/routes`, `app/templates`)
- Database: Postgres for Docker deployment (SQLite migration script supported)
- Search: FTS (`lecture_chunks` + backend retrieval pipeline)

## Key directories
- `app/`: Flask app, services, models
- `next_app/`: Next.js frontend
- `docker/`: backend/frontend Dockerfiles
- `migrations/`: SQL migrations
- `scripts/`: init, migration, verification tools
- `docs/`: setup and operation docs

## Runtime flow
1. Browser -> Next.js web (`:4000`)
2. Next.js proxy (`/api/proxy/*`) -> Flask API (`:5000`)
3. Flask services -> Postgres

## Main entrypoints
- Production backend: `wsgi.py` (Gunicorn)
- Local fallback backend: `run.py`
- Compose: `docker-compose.yml`
