# Environment Variables

This project supports two runtime profiles.

## 1) Local development (host-run backend/frontend)
- Backend: `.env`
- Frontend: `next_app/.env.local`

Create from templates:
```bash
cp .env.example .env
cp .env.docker.example .env.docker
cp next_app/.env.local.example next_app/.env.local
```

Recommended local keys in `.env`:
```dotenv
FLASK_CONFIG=development
FLASK_DEBUG=1
# Optional override. If unset, dev scripts derive URL from .env.docker POSTGRES_*.
DATABASE_URL=postgresql+psycopg://exam:<POSTGRES_PASSWORD>@127.0.0.1:5432/exam_manager
SEARCH_BACKEND=postgres
CORS_ALLOWED_ORIGINS=http://localhost:4000
```

## 2) Docker compose (full stack)
Main file:
- `.env.docker`: used by `docker compose --env-file .env.docker`

Create from template:
```bash
cp .env.docker.example .env.docker
```

Required for full stack:
| Key | Purpose |
| --- | --- |
| `SECRET_KEY` | Flask session secret |
| `JWT_SECRET_KEY` | JWT signing secret |
| `POSTGRES_PASSWORD` | Postgres password |

## Common optional keys
| Key | Purpose | Default |
| --- | --- | --- |
| `POSTGRES_USER` | Postgres user | `exam` |
| `POSTGRES_DB` | Postgres database | `exam_manager` |
| `CORS_ALLOWED_ORIGINS` | Allowed browser origins | `http://localhost:4000` |
| `JWT_COOKIE_SECURE` | Force secure JWT cookie (`1` for HTTPS only) | `0` |
| `JWT_ACCESS_TOKEN_EXPIRES_MINUTES` | Access token lifetime (minutes) | `720` |
| `JWT_REFRESH_WINDOW_MINUTES` | Sliding refresh window (minutes) | `30` |
| `NEXT_PUBLIC_SITE_URL` | Next base URL | `http://localhost:4000` |
| `NEXT_PUBLIC_APP_URL` | Next base URL fallback | `http://localhost:4000` |
| `GEMINI_API_KEY` | Enable AI features | unset |
| `KEEP_PDF_AFTER_INDEX` | Keep uploaded lecture PDFs after indexing (`1` keeps, `0` deletes) | `0` |
| `RETRIEVAL_MODE` | Retrieval mode (`bm25`, `hybrid_rrf`) | `bm25` |
| `SEARCH_BACKEND` | Search backend (`auto`, `postgres`) | `postgres` (docker env) |
| `SEARCH_PG_QUERY_MODE` | Postgres tsquery mode (`websearch`, `plainto`, `to_tsquery`) | `websearch` |
| `SEARCH_PG_TRGM_ENABLED` | Enable pg_trgm fallback (`0/1`) | `0` |
| `CLASSIFIER_REQUIRE_VERBATIM_QUOTE` | Keep evidence only when quote is verbatim | `1` |
| `CLASSIFIER_REQUIRE_PAGE_SPAN` | Keep evidence only when page span exists | `1` |
| `CLASSIFIER_DEBUG_LOG` | 분류 단계 상세 로그(`CLASSIFIER_*`) 출력 (`0/1`) | `0` |

## Notes
- Restart backend/frontend after `.env` changes.
- Restart containers after `.env.docker` changes.
- `scripts/dev-db` reads `.env.docker` by default (same DB volume as docker full stack) and exposes `127.0.0.1:5432` for host backend.
- Use `DEV_DB_COMPOSE_FILE=docker-compose.local.yml` when you want an isolated local DB volume.
- Do not commit `.env` or `.env.docker`.
