# Exam Manager - Next.js UI

This Next.js app provides the primary management and practice UI. It communicates with the Flask backend through the `/api/proxy/*` route.

## Requirements
- Node.js 18+
- Flask API running (default: `http://127.0.0.1:5000`)

## Setup
1) Create `next_app/.env.local`:

```dotenv
FLASK_BASE_URL=http://127.0.0.1:5000
# NEXT_PUBLIC_SITE_URL=http://localhost:4000
# NEXT_PUBLIC_APP_URL=http://localhost:4000
```
or
```bash
cp next_app/.env.local.example next_app/.env.local
```

2) Install dependencies and run the dev server:

```bash
npm install
npm run dev
```

From project root, you can also run:
```bash
./scripts/dev-frontend
```

3) Open:

http://localhost:4000/lectures

## Notes
- `FLASK_BASE_URL` is required for the proxy to reach Flask.
- `NEXT_PUBLIC_SITE_URL`/`NEXT_PUBLIC_APP_URL` are only needed for SSR base URL overrides.
