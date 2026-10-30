# VoiceDesk Realty

VoiceDesk Realty is an existing Next.js frontend and FastAPI backend for public property browsing, customer accounts, bookings, and Bolna Web Call sessions. The deployment target is two Vercel projects connected to this GitHub repository, with Neon PostgreSQL as the hosted database.

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

Open `http://localhost:3000`; the API health check is `http://localhost:8000/api/health`. Local development uses SQLite when `DATABASE_URL` is blank. The seed command is explicit and only creates fictional demo listings.

## Deployment overview

- Frontend: Vercel project rooted at `frontend`.
- Backend: separate Vercel project rooted at `backend`, using the existing `app.py` FastAPI application and `requirements.txt`. Vercel's Python runtime discovers the application from this supported root entrypoint; no persistent Uvicorn process, Render service, or Render pre-deploy command is used.
- Database: Neon PostgreSQL. Production never falls back to SQLite, and Vercel does not provision the database for this project.

Both Vercel projects can connect to the same GitHub repository and deploy from `main`. No production deployment or Neon connection has been performed from this workspace.

## Neon database setup and migrations

1. Create a Neon project and database, then choose a region close to the Vercel deployment.
2. In Neon Console, open **Connect** and copy the pooled connection string for the application. The pooler hostname contains `-pooler`; set that full URI as the backend Vercel project's `DATABASE_URL`. The application normalizes PostgreSQL URI schemes to Psycopg 3.
3. Keep the Neon connection URI private and enter it only in Vercel environment settings or a protected local environment. Do not put it in source control or chat.
4. Before the first production deploy, run migrations deliberately from a trusted machine with Python requirements installed and `DATABASE_URL` temporarily set to the Neon **direct** connection URI. From `backend`, run:

   ```powershell
   python -m alembic -c alembic.ini upgrade head
   python -m alembic -c alembic.ini current
   ```

   Use the direct Neon connection for Alembic. Use the pooled connection URI for serverless application traffic. Migrations are never run at application import or per request.
5. Verify `GET https://<backend-project>.vercel.app/api/health` returns `{"status":"ok","database":"ok"}`. The endpoint checks the database; it returns HTTP 503 if the database query fails.
6. Demo data is separate from schema setup. To insert fictional listings into a test database, run `python seed_database.py` with that database selected. Production seeding requires `--confirm-production-demo-seed`; do not use it for real inventory.

Vercel Functions use SQLAlchemy `NullPool` so each short-lived function environment does not retain its own connection pool. Use Neon's pooled URI for the app and direct URI for migration tooling. Neon free-tier compute can suspend while idle and has plan-specific storage, compute, and usage limits; cold database wakeups can add latency. Check Neon’s current plan page before relying on free-tier limits.

## Vercel project settings

### Frontend project

- Framework preset: Next.js (automatic detection).
- Root Directory: `frontend`.
- Build command: `npm run build` (or Vercel's detected Next.js build command).
- Install command: `npm install`.
- Production branch: `main`.
- Current production frontend URL: `https://voicedesk-realty-wr74.vercel.app` (use this exact origin for backend `FRONTEND_URL` unless the Vercel domain changes).
- Environment variable: `NEXT_PUBLIC_API_URL` = the backend project's HTTPS origin only, for example `https://<backend-project>.vercel.app`; do not append `/api` or a path. Set for Production and for Preview only when that Preview uses a backend configured to trust its exact origin.
- Redeploy the frontend after changing this build-time variable.

`frontend/.env.example` contains only the local-development API origin. The production Next.js build fails clearly if `NEXT_PUBLIC_API_URL` is missing or is not an HTTPS origin. Local development retains its `http://localhost:8000` fallback.

### Backend project

- Framework/runtime: Vercel Python runtime; FastAPI is detected from `backend/app.py` and `backend/requirements.txt`.
- Root Directory: `backend`.
- Python version: `3.13` (declared in `backend/.python-version`; Vercel documents selecting a supported minor version in this file).
- Build command: leave unset/use Vercel's automatic Python dependency installation from `requirements.txt`.
- Output directory: leave unset.
- Production branch: `main`.
- Do not configure a Uvicorn start command. Vercel serves the exported `app` as a Python Function.
- Set the backend environment variables below for Production. Set `APP_ENV=production`, `DATABASE_URL` to Neon’s pooled URI, `FRONTEND_URL` to the exact frontend origin, `COOKIE_SECURE=true`, and `COOKIE_SAMESITE=none`.
- Redeploy the backend after changing environment variables.

Vercel's Python runtime currently supports FastAPI and automatically serves the app at the configured project root as a Function. Functions have execution and bundle limits; this backend uses synchronous SQLAlchemy sessions per request, no long-lived worker, and no import-time migration or seeding. Confirm the current Vercel Python runtime limits for the account before launch.

## Environment variables

Backend Vercel project:

- Required: `APP_ENV`, `DATABASE_URL`, `FRONTEND_URL`, `COOKIE_SECURE`, `COOKIE_SAMESITE`.
- Optional voice: `BOLNA_WEB_CALL_ENABLED`, `BOLNA_API_KEY`, `BOLNA_AGENT_ID`, `BOLNA_WEBHOOK_SECRET`.
- `BOLNA_WEB_CALL_ENABLED` defaults to `false`. A previously exposed Bolna credential must not be reused; voice remains disabled until a replacement key and intended agent are configured securely and the feature is explicitly enabled.
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, and `EMAIL_PROVIDER_API_KEY` are placeholders only. Google Calendar, email sending, and password-reset completion are not implemented.

Frontend Vercel project:

- `NEXT_PUBLIC_API_URL` only. Never put private credentials in `NEXT_PUBLIC_*` variables.

Use exact origins: `FRONTEND_URL` must be the scheme and host of the frontend only, without a path or trailing slash. Credentialed CORS allows that one origin. Unsafe browser requests validate `Origin`; production rejects state-changing requests without it, except the Bolna webhook, which uses its separate shared secret. Cookies are HttpOnly; production requires Secure and `SameSite=None` for cross-origin requests.

Browsers can restrict cross-site cookies. For more reliable production authentication, use frontend and API custom hostnames under the same site (for example `app.example.com` and `api.example.com`) and test login persistence in the target browsers. Vercel Preview URLs are not automatically trusted by the exact-origin CORS policy; configure a corresponding backend environment with the exact Preview origin before testing Preview authentication.

## API and feature status

- Public home dashboard, property search, and property details do not require login.
- Registration assigns the customer role; passwords are bcrypt-hashed, and opaque server-side sessions use HttpOnly cookies.
- Saved homes, bookings, call history, and Bolna session creation require authentication and are scoped to the current customer. Agent and administrator sample endpoints enforce role checks.
- Bookings are requests, not external agent confirmations. No Google Calendar event is created.
- Bolna session creation uses the backend-only master key. Do not claim real call success until it has been tested from the deployed browser with a rotated key and configured agent.
- Google Calendar, transactional email, and password reset are not implemented. The reset endpoint reports that email setup/workflow is unavailable; it does not pretend to send a message.
- Agent lead views and full agency administration are incomplete placeholders.

## Troubleshooting

- **Registration says “Failed to fetch” / API unreachable:** confirm the frontend Production `NEXT_PUBLIC_API_URL` is the backend HTTPS origin, redeploy the frontend, and check the backend's `/api/health` endpoint.
- **CORS error:** set backend `FRONTEND_URL` to the exact browser origin, without a trailing slash or path, then redeploy the backend. Preview origins require their own exact setting.
- **Health returns 503 / database connection failure:** confirm backend `DATABASE_URL` is set to the correct Neon pooled URI, the Neon project/database/role are active, and outbound connections are available.
- **Migration fails:** use Neon’s direct (non-pooled) connection URI for the deliberate Alembic command and verify the database role can create/alter schema objects.
- **Login does not persist:** confirm HTTPS, `COOKIE_SECURE=true`, `COOKIE_SAMESITE=none`, credentialed requests, exact CORS origin, and target-browser cross-site cookie policy. Same-site custom domains are recommended.
- **Voice is unavailable:** check that replacement Bolna credentials and the intended agent are configured on the backend, then explicitly enable `BOLNA_WEB_CALL_ENABLED`; browser microphone permission and a real call still require separate verification.

## Checks

Run checks from the project folders:

```powershell
cd D:\voicedesk\backend
python -m pytest -q -p no:cacheprovider
python -m py_compile app.py seed_database.py create_user.py alembic\env.py alembic\versions\0001_initial_schema.py alembic\versions\0002_call_records.py
python -m alembic -c alembic.ini upgrade head

cd D:\voicedesk\frontend
npm run typecheck
npm run lint
npm test
$env:NEXT_PUBLIC_API_URL='https://api.example.invalid'
npm run build
```

The exact validation outcomes and any checks not run are recorded in `IMPROVEMENT.md`.

Official references: [Vercel FastAPI deployment](https://vercel.com/docs/frameworks/backend/fastapi), [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python), [Neon connection pooling](https://neon.com/docs/connect/connection-pooling).
