# Environment Variables

This project uses Docker-first execution.

## Main file
- `.env.docker`: used by `docker compose --env-file .env.docker`

Create from template:
```bash
cp .env.docker.example .env.docker
```

## Required
| Key | Purpose |
| --- | --- |
| `SECRET_KEY` | Flask session secret |
| `JWT_SECRET_KEY` | JWT signing secret |
| `POSTGRES_PASSWORD` | Postgres password |

## Common Optional
| Key | Purpose | Default |
| --- | --- | --- |
| `POSTGRES_USER` | Postgres user | `exam` |
| `POSTGRES_DB` | Postgres database | `exam_manager` |
| `CORS_ALLOWED_ORIGINS` | Allowed browser origins | `http://localhost:4000` |
| `NEXT_PUBLIC_SITE_URL` | Next base URL | `http://localhost:4000` |
| `NEXT_PUBLIC_APP_URL` | Next base URL fallback | `http://localhost:4000` |
| `GEMINI_API_KEY` | Enable AI features | unset |

## Notes
- Restart containers after env changes.
- Do not commit `.env.docker`.
