# VoiceDesk Realty

VoiceDesk Realty is an existing Next.js frontend and FastAPI API for public property browsing, customer accounts, bookings, and protected voice features. This hackathon deployment uses the existing frontend on Vercel and the backend on Render.

## Local development (PowerShell)

Backend terminal:

```powershell
cd D:\voicedesk\backend
Copy-Item .env.example .env
python -m pip install -r requirements.txt
python -m uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Frontend terminal:

```powershell
cd D:\voicedesk\frontend
npm install
npm run dev
```

Open `http://localhost:3000`; API health is `http://localhost:8000/api/health`. A blank or missing `DATABASE_URL` uses `backend/voicedesk.db` (SQLite). Tables are created idempotently when FastAPI starts. To add fictional listings locally, run `python seed_database.py` from `backend` after starting the app once.

## Hackathon deployment: Render backend + Vercel frontend

A `render.yaml` Blueprint is included for a free Render web service. In Render, create/update the Blueprint from this repository and deploy the `voicedesk-realty-api` service. It uses:

- Root directory: `backend`
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Health check: `/api/health`
- No Alembic pre-deploy command is needed: the app creates missing tables on startup.

### Render environment

The Blueprint sets these non-secret values:

- `APP_ENV=production`
- `FRONTEND_URL=https://voicedesk-realty-wr74.vercel.app`
- `COOKIE_SECURE=true`
- `COOKIE_SAMESITE=none`
- `BOLNA_WEB_CALL_ENABLED=false`

`DATABASE_URL` is optional for this temporary demo. Leave it unset to use SQLite, or set it in Render's environment to a PostgreSQL connection URL to use PostgreSQL. The SQLite file is on Render's ephemeral filesystem: data may be lost on service restart, redeploy, or instance replacement. This is suitable for a temporary demo, not durable production data. No Neon database or paid database is required to start this demo.

To populate fictional listings on the hosted service, run `python seed_database.py --confirm-production-demo-seed` from a Render Shell after the first start. Seeding is an explicit separate step and does not run on import or startup.

### Vercel frontend environment

In the existing Vercel frontend project, set the build-time variable:

- `NEXT_PUBLIC_API_URL` = the Render backend HTTPS origin, for example `https://voicedesk-realty-api.onrender.com` (origin only; do not append `/api`).

Redeploy the frontend after changing this value. If the Render service name or generated domain differs, use the actual Render origin. The backend CORS allowlist must exactly match the browser frontend origin; `render.yaml` currently sets the requested production Vercel origin. Update `FRONTEND_URL` in Render if that domain changes, then redeploy the backend.

Separate `vercel.app` and `onrender.com` domains use cross-site cookies. Production cookies are configured as Secure and SameSite=None, but browser third-party-cookie restrictions can still affect login persistence. Verify authentication in the target browser.

## Database and migrations

The application supports PostgreSQL when `DATABASE_URL` is provided and normalizes common `postgres://` and `postgresql://` URLs to Psycopg 3. It configures a small connection pool. With no URL, it uses SQLite with `check_same_thread=False`, suitable for this temporary Render demo. Startup uses SQLAlchemy `create_all` only for missing tables. Alembic remains available for deliberate schema migrations but is not required to start this deployment. Alembic reads the same `DATABASE_URL` configuration as the application.

## Feature status and limitations

- Public dashboard, property search, and listing detail routes remain available without login.
- Registration defaults to customer, passwords are hashed, and protected features use authenticated sessions.
- Bookings are stored requests; no calendar event or external agent confirmation is implied.
- Bolna calling stays disabled (`BOLNA_WEB_CALL_ENABLED=false`). No Bolna credentials are required or exposed to the browser.
- Google Calendar, email delivery, and full password-reset email delivery are not implemented. Agent/admin features remain limited to the existing API behavior.
- `/api/health` checks database connectivity and returns `{"status":"ok","database":"ok"}` when available. Optional voice and other integrations are not part of the health check.

## Backend checks

From `backend`:

```powershell
python -m pytest -q -p no:cacheprovider
python -m py_compile app.py test_app.py seed_database.py
```

See `IMPROVEMENT.md` for the actual results from this deployment-preparation pass. No deployment or GitHub push is performed from this workspace.
