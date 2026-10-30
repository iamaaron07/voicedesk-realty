# VoiceDesk Realty — implementation and verification status

**Updated:** 2026-10-30

**Deployment target:** Next.js on Vercel, FastAPI on Vercel Python Functions, Neon PostgreSQL.

**Deployment status:** code and configuration prepared locally; no GitHub push, Vercel deployment, Neon project, production migration, or external integration was performed.

## Changes in this deployment-readiness pass

- Updated `backend/app.py` to use SQLAlchemy `NullPool` when Vercel environment variables are present. This avoids retaining a small pool in every serverless function instance; the app should use Neon's pooled connection URI.
- `/api/health` now reports both application and database status (`{"status":"ok","database":"ok"}`) and responds with 503 when the database query fails.
- Bolna calling is now disabled by default in application checks and `backend/.env.example`. The ignored local `backend/.env` was sanitized without displaying values: Bolna key, agent, and webhook secret entries are empty and the feature flag is false. Do not reuse the previously exposed key; rotate it with Bolna before any voice test.
- Production demo seeding now also recognizes Vercel platform variables and keeps its explicit confirmation guard when `APP_ENV` is absent.
- Added regression tests for Vercel `NullPool` selection, default-disabled voice, and the health response.
- Added `frontend/.env.example` with a local-only API origin. `.gitignore` now ignores Vercel metadata, frontend coverage, and TypeScript build info.
- Centralized frontend API origin handling in `frontend/src/app/api-client.ts`: localhost is selected only in development, production requires the configured HTTPS `NEXT_PUBLIC_API_URL`, and a unit test covers both behaviors.
- Set `backend/.python-version` to Vercel's supported minor-version format (`3.13`).
- Replaced Render deployment guidance in `README.md` with Vercel frontend/backend and Neon PostgreSQL setup, migration instructions, exact environment variable names, cookie/CORS guidance, feature status, and troubleshooting.
- Removed the obsolete `render.yaml`; no Render resource is part of the target architecture.

## Architecture and Vercel settings

Both Vercel projects use the same GitHub repository and deploy from `main`:

**Frontend project**

- Root Directory: `frontend`.
- Framework: Next.js, automatically detected.
- Install: `npm install`; Build: `npm run build` (or Vercel's detected Next.js command).
- Environment: `NEXT_PUBLIC_API_URL`, set to the backend HTTPS origin without `/api`, path, or trailing slash. Set Production and only configure Preview when its exact origin is allowed by the matching backend environment.
- Redeploy after changing this build-time variable.

**Backend project**

- Root Directory: `backend`.
- Runtime: Vercel Python; `backend/app.py` exports the FastAPI `app`, and `requirements.txt` declares dependencies. The current Vercel FastAPI/Python convention supports an `app.py` entrypoint at the project root. No Uvicorn start command, persistent process, or custom Vercel config is required for this layout.
- Python: 3.13 (`backend/.python-version`).
- Build/output settings: leave automatic; Vercel installs Python dependencies from `requirements.txt`.
- Environment variables: `APP_ENV`, `DATABASE_URL`, `FRONTEND_URL`, `COOKIE_SECURE`, `COOKIE_SAMESITE`; optional `BOLNA_WEB_CALL_ENABLED`, `BOLNA_API_KEY`, `BOLNA_AGENT_ID`, `BOLNA_WEBHOOK_SECRET`.
- Production values: `APP_ENV=production`, Neon pooled `DATABASE_URL`, exact frontend origin in `FRONTEND_URL`, `COOKIE_SECURE=true`, `COOKIE_SAMESITE=none`, `BOLNA_WEB_CALL_ENABLED=false` until a replacement Bolna key and agent are verified.
- Redeploy after changing variables.

The backend defaults hosted Vercel/Render environments to production if `APP_ENV` is omitted. Its module import creates an engine but does not connect, create tables, migrate, or seed. A missing production `DATABASE_URL` fails safely; production SQLite is rejected. Alembic reads `DATABASE_URL`, the same variable used by the app. The Vercel-specific SQLAlchemy `NullPool` branch is unit-tested, but no Vercel CLI build or deployed function invocation was run in this environment.

## Neon setup and migration procedure

1. Create a Neon project/database in a region close to Vercel.
2. For the backend Production `DATABASE_URL`, copy the pooled PostgreSQL URI from Neon Console (**Connect**, pooling enabled; pooled host includes `-pooler`). Neon recommends pooled connections for serverless traffic and direct connections for schema migrations.
3. Before first deployment and after schema changes, use a protected workstation/CI environment with the Neon direct (non-pooled) URI set as `DATABASE_URL`, then run from `backend`:

   ```powershell
   python -m alembic -c alembic.ini upgrade head
   python -m alembic -c alembic.ini current
   ```

4. Configure the backend Vercel variables and deploy. Check `/api/health`; it queries the configured database and returns 503 if unavailable.
5. Run `python seed_database.py` only against a chosen development/test database. It creates fictional data. Production requires the explicit `--confirm-production-demo-seed` flag and should not be seeded with fictional listings unless intentionally desired.

No Neon URL or credential is stored in this repository. Neon connectivity, production migrations, backups, and free-tier account limits remain to be verified by the account owner. Neon free compute can suspend while idle; its current quotas/limits should be checked before launch.

## Security and feature status

- CORS allows the exact configured `FRONTEND_URL` with credentials. State-changing requests reject an untrusted browser `Origin`; production rejects missing Origin except for the separately secret-validated Bolna webhook.
- Session cookies are HttpOnly; production requires Secure and supports `SameSite=None` for cross-origin requests. Third-party cookie restrictions may affect separate `vercel.app` project domains. Same-site custom frontend/API hostnames are recommended and browser login persistence needs a real deployed-browser check.
- The browser uses only `NEXT_PUBLIC_API_URL`; private database/Bolna credentials remain backend variables. `NEXT_PUBLIC_API_URL` is validated during production build.
- Customer role is assigned during registration. Saved properties, bookings, voice sessions, and personal call history require authentication; agent/admin sample endpoints enforce role checks.
- Public dashboard and property APIs remain public. Booking status is a local request, not a calendar or agent confirmation.
- Bolna call session requests are authenticated and use a backend key; calling defaults off. This pass did not contact Bolna or start a call. Rotate the previously exposed key, configure the intended agent, then explicitly enable the feature and test from a browser.
- Google Calendar, email delivery, and complete password reset are not implemented. The password-reset endpoint does not claim to send email. Agent leads and agency administration are limited placeholders.
- In-memory request/voice rate limits are not distributed across serverless instances. Add a shared rate-limit store before relying on them at scale.

## Validation performed in this pass

- `cd backend; python -m pytest -q -p no:cacheprovider`: **20 passed**.
- `cd backend; python -m py_compile app.py seed_database.py create_user.py alembic\env.py alembic\versions\0001_initial_schema.py alembic\versions\0002_call_records.py`: passed.
- Fresh isolated SQLite database: Alembic upgrade ran twice successfully; `alembic current` reported `0002_call_records (head)`; the explicit demo seed ran twice and a count query confirmed 30 fictional properties. The temporary database was removed. No Neon database was used.
- Vercel-mode production import check with a nonconnecting placeholder PostgreSQL URL: passed; 28 routes loaded, driver normalized to Psycopg 3, `NullPool` selected, and no database connection was attempted.
- `cd frontend; npm run typecheck`: passed.
- `cd frontend; npm run lint`: passed (ESLint; Windows execution took longer than 30 seconds but exited 0).
- `cd frontend; npm test`: **11 passed** across 2 files. The first sandboxed Vitest attempt failed because Windows denied esbuild's child process (`spawn EPERM`); rerun with process permission passed.
- `cd frontend; $env:NEXT_PUBLIC_API_URL='https://api.example.invalid'; npm run build`: passed on Next.js 15.5.28. The placeholder URL was used only for build validation and is not a production URL.
- `git diff --check`: passed; Git reported only configured LF/CRLF normalization warnings.
- API coverage in backend tests includes public property search, health, registration/login/logout/session invalidation, role boundaries, authenticated voice endpoint behavior and master-key isolation in stubbed transport, webhook secret handling, booking idempotency/conflict/cancel/reschedule, cookies, CORS and production configuration helpers.
- No browser/device emulation, Vercel CLI build/deploy, external database connection, Neon migration, live credential check, Bolna session, real voice call, or Calendar/email provider test was performed.

## Remaining manual checks

1. Create/configure Neon, save its pooled URI as backend Production `DATABASE_URL`, and run the migration commands above using a direct URI before initial use.
2. Create two Vercel projects from the same GitHub repository with root directories `frontend` and `backend` respectively; connect both to `main` for push-triggered deployment.
3. Set backend Production variables (`APP_ENV`, `DATABASE_URL`, `FRONTEND_URL`, `COOKIE_SECURE`, `COOKIE_SAMESITE`) in Vercel. Keep Bolna disabled and omit credentials until a replacement is configured.
4. Set frontend Production `NEXT_PUBLIC_API_URL` to the deployed backend origin; redeploy frontend. Ensure backend `FRONTEND_URL` exactly matches the frontend's final origin; redeploy backend.
5. Verify `/api/health`, public listing search/detail, registration, login, persisted account access, logout, protected voice redirect, and microphone flow in a real browser. Browser cookie policy may require same-site custom domains.
6. Confirm deployments are healthy and check Vercel/Neon current free-tier usage and execution limits. No push or deployment has been initiated.

## Final validation results

Validation commands and outcomes listed above were run during this pass; only external, deployment, and browser checks listed above remain outstanding.
