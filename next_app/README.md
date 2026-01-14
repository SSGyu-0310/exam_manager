# Exam Manager - Next.js UI

This Next.js app provides the primary management and practice UI. It communicates with the Flask backend through the `/api/proxy/*` route.

## Requirements
- Node.js 18+
- Flask API running (default: `http://127.0.0.1:5000`)

## Setup
1) Create `next_app/.env.local`:

```dotenv
FLASK_BASE_URL=http://127.0.0.1:5000
# NEXT_PUBLIC_SITE_URL=http://localhost:3000
# NEXT_PUBLIC_APP_URL=http://localhost:3000
```

2) Install dependencies and run the dev server:

```bash
npm install
npm run dev
```

3) Open:

http://localhost:3000/lectures

## Notes
- `FLASK_BASE_URL` is required for the proxy to reach Flask.
- `NEXT_PUBLIC_SITE_URL`/`NEXT_PUBLIC_APP_URL` are only needed for SSR base URL overrides.
