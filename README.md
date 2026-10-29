# VoiceDesk Realty

VoiceDesk Realty is an existing Next.js frontend and FastAPI backend for public property browsing, customer accounts, bookings, and Bolna Web Call sessions. Production deployment is split between Vercel (frontend), Render (API), and managed PostgreSQL.

## Local development (PowerShell)

Backend terminal:

```powershell
cd D:\voicedesk\backend
Copy-Item .env.example .env
python -m pip install -r requirements.txt
python -m alembic -c alembic.ini upgrade head
python seed_database.py
python -m uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Frontend terminal:

```powershell
cd D:\voicedesk\frontend
npm install
npm run dev
```

Open `http://localhost:3000`; API health is at `http://localhost:8000/api/health`. Local development uses SQLite when `DATABASE_URL` is blank. Copying `.env.example` is optional if you prefer the defaults. Demo data is created only by the explicit `python seed_database.py` command.

## Production architecture and Render setup

`render.yaml` defines a free API web service. Connect the existing repository to Render as a Blueprint, set the backend Root Directory to `backend` (already declared), and provide the environment variables listed below in the Render dashboard. This Blueprint does not create a PostgreSQL database. Configure a separate PostgreSQL database and set its connection string in `DATABASE_URL` before starting the backend; production startup fails when `DATABASE_URL` is missing. A free Render web service does not include a database, and Render's free PostgreSQL databases expire after 30 days.

Render service commands:

```text
Build:       pip install -r requirements.txt
Pre-deploy:  python -m alembic -c alembic.ini upgrade head
Start:       uvicorn app:app --host 0.0.0.0 --port $PORT
Health:      /api/health
```

The migration command remains recorded in `render.yaml`, but Render documents pre-deploy commands as available only for paid web services, private services, and background workers. Therefore, on this free web service it will not run automatically. Apply migrations from a trusted environment with the production `DATABASE_URL` configured, running `python -m alembic -c alembic.ini upgrade head` from `backend`, before deploying schema-dependent changes. Do not run the demo seed command against production inventory unless fictional listings are explicitly intended. The safe production override is `python seed_database.py --confirm-production-demo-seed`.

Set these Render variables; enter secret/URL values only in Render, never in source control or chat:

- `APP_ENV=production`
- `DATABASE_URL` — managed PostgreSQL connection string; `postgres://` and `postgresql://` are normalized to Psycopg 3.
- `FRONTEND_URL` — exact Vercel frontend origin, for example `https://your-site.vercel.app` (origin only, no path or trailing slash).
- `COOKIE_SECURE=true`
- `COOKIE_SAMESITE=none` for the separate Vercel and Render hostnames. Prefer custom frontend/API domains under the same registrable domain; browsers may restrict third-party cookies between unrelated `vercel.app` and `onrender.com` sites.
- `BOLNA_WEB_CALL_ENABLED=false` initially. Set `BOLNA_API_KEY` and `BOLNA_AGENT_ID` in Render and enable it only after validating the intended account/agent. For post-call summaries, set `BOLNA_WEBHOOK_SECRET` and configure the Bolna webhook URL/header.

The backend requires `DATABASE_URL` and an HTTPS `FRONTEND_URL` in production; it rejects production SQLite and insecure cookies. The SQLAlchemy pool is capped at two connections per process with no overflow. Use a managed connection pooler if the database limit is low or the Render service scales beyond one process.

## Vercel frontend setup

Create a Vercel project for the `frontend` directory (Root Directory: `frontend`). Set the following environment variable for Production and Preview as appropriate, then redeploy after changing it:

- `NEXT_PUBLIC_API_URL` — the Render service’s HTTPS origin, with no API path (for example `https://your-api.onrender.com`).

The production build fails if this variable is missing; local development keeps the `http://localhost:8000` fallback. After the Vercel domain is known, set the exact same origin in Render’s `FRONTEND_URL`, then redeploy both services if their environment changed. With separate Render/Vercel domains, retain `COOKIE_SAMESITE=none` and `COOKIE_SECURE=true`; a shared custom domain is recommended for browser cookie compatibility.

Official references: [Render FastAPI deployment](https://render.com/docs/deploy-fastapi), [Render pre-deploy commands](https://render.com/docs/deploys), and [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python).

## Environment variable names

Backend: `APP_ENV`, `DATABASE_URL`, `FRONTEND_URL`, `COOKIE_SECURE`, `COOKIE_SAMESITE`, `BOLNA_API_KEY`, `BOLNA_AGENT_ID`, `BOLNA_WEB_CALL_ENABLED`, `BOLNA_WEBHOOK_SECRET`. `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, and `EMAIL_PROVIDER_API_KEY` are retained as placeholders only; Google Calendar and email/password-reset integrations are not implemented.

Frontend: `NEXT_PUBLIC_API_URL`.

Never put backend credentials in `NEXT_PUBLIC_*` variables. Keep local `.env` files untracked.

## Authentication and integration status

Registration assigns the customer role, passwords are bcrypt-hashed, and sessions are opaque HttpOnly cookies stored as server-side digests. CORS is restricted to `FRONTEND_URL`; state-changing requests reject an explicitly untrusted `Origin`, and production requires the browser `Origin` header except for the Bolna webhook (which uses its own secret). No real Bolna call is claimed by this project status. Google Calendar and email workflows are not connected. Booking records are local requests (status `requested` or `rescheduled`); they do not imply a calendar event or external agent confirmation.

Review `IMPROVEMENT.md` for the latest verified checks and production limitations. Tests/build:

```powershell
cd D:\voicedesk\backend
python -m pytest -q -p no:cacheprovider
cd D:\voicedesk\frontend
npm run typecheck
npm run lint
npm test
$env:NEXT_PUBLIC_API_URL='https://api.example.invalid'
npm run build
```
