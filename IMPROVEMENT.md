# VoiceDesk Realty — implementation and verification status

**Updated:** 2026-10-29

## Production deployment readiness update (2026-10-29)

Target architecture is Next.js on Vercel, FastAPI on Render, and managed PostgreSQL. No deployment or external service changes were made.

- Removed table creation, demo listing insertion, and demo agency/agent insertion from `app.py` import. Schema changes now go through Alembic; demo listing generation is a separate `seed_database.py` command and requires an explicit production override.
- Production startup requires `APP_ENV=production`, a PostgreSQL `DATABASE_URL`, a valid HTTPS `FRONTEND_URL`, and secure cookies. SQLite remains the local development fallback only. Render `postgres://` and `postgresql://` URLs are normalized to the installed Psycopg 3 driver.
- PostgreSQL SQLAlchemy pools are capped at 2 connections per worker with no overflow and pre-ping. Alembic online and offline modes now resolve the same `DATABASE_URL` as the application.
- `/api/health` checks a database query and returns 503 if it cannot reach the database. Production CORS is exact-origin credentialed CORS. State-changing requests reject untrusted origins and production requests without an Origin header; Bolna webhook auth remains shared-secret based.
- Cookies are HttpOnly; production enforces `COOKIE_SECURE=true` and supports configurable `COOKIE_SAMESITE` (Render template uses `none` for separate Vercel/Render sites). Third-party cookie restrictions remain a browser/platform consideration; use same-site custom domains when possible.
- Bolna master credentials remain backend-only. The session route still requires an authenticated user. The webhook still requires `BOLNA_WEBHOOK_SECRET` and matching configured agent ID. No Bolna request/call was performed during this deployment-readiness task.
- Production frontend builds now require `NEXT_PUBLIC_API_URL`; on Vercel it must be HTTPS. Local development keeps its localhost fallback. The dashboard now shows a clear property API outage message.
- Added `render.yaml` with backend root, build/pre-deploy migration/start commands, health check, secure production settings, and secret placeholders. It does not provision a database. The pre-deploy command needs a Render plan that supports pre-deploy commands.

### Validation for this update

- Backend test suite: **16 passed** (including production database URL/driver/pool checks, HTTPS origin and cookie settings, database health, rejected foreign Origin, authenticated Bolna request construction/key isolation, webhook authentication, truthful integration status, and production seed guard).
- Frontend TypeScript: passed.
- Frontend ESLint: passed.
- Frontend Vitest: **9 passed**.
- Frontend Next.js production build: passed with `NEXT_PUBLIC_API_URL` set to a safe example HTTPS origin for compile-time validation; no real API URL is stored in the project.
- Backend Python compilation: passed. Fresh SQLite Alembic migration and repeat upgrade passed. Separate isolated migration + seed run produced 30 fictional properties. Importing `app` against a fresh SQLite path did not create a database file.
- Production-mode import configuration check passed using a nonconnecting test PostgreSQL URL: Psycopg 3 driver, pool size 2, overflow 0, secure cookie, and `SameSite=None` were selected without opening a DB connection.
- Fresh managed PostgreSQL connectivity/migration has not been tested. Render must apply migrations after its environment is configured.

### Remaining deployment tasks and risks

- Configure Render `DATABASE_URL` with the managed PostgreSQL connection string, `FRONTEND_URL` with the final Vercel origin, and apply migrations through Render's pre-deploy command. No production DB URL or credentials are stored in this repo.
- Configure Vercel `NEXT_PUBLIC_API_URL` with the Render API origin and redeploy. Set the same exact origin in Render `FRONTEND_URL`; redeploy the API after changes.
- Configure Bolna credentials and webhook in Render/agent settings only if needed. The deployment template disables voice by default and contains no credentials. No real voice call is claimed.
- Load reviewed production property inventory separately. The seed creates fictional demo listings, not real estate data. Do not run it in production unless fictional listings are intentionally wanted.
- In-memory auth/voice rate limits are not shared across Render instances. Add a shared rate-limit store before scaling. Booking overlap checks now use a PostgreSQL transaction advisory lock; a live multi-worker PostgreSQL test has not been run.
- Google Calendar, email, and password reset delivery are not implemented. Existing environment placeholders do not activate these integrations.

### Deployment settings and commands

Render Blueprint service commands:

```text
Root Directory: backend
Build:          pip install -r requirements.txt
Pre-deploy:     python -m alembic -c alembic.ini upgrade head
Start:          uvicorn app:app --host 0.0.0.0 --port $PORT
Health check:   /api/health
```

Set Render backend variables by name: `APP_ENV`, `DATABASE_URL`, `FRONTEND_URL`, `COOKIE_SECURE`, `COOKIE_SAMESITE`, `BOLNA_WEB_CALL_ENABLED`, `BOLNA_API_KEY`, `BOLNA_AGENT_ID`, and `BOLNA_WEBHOOK_SECRET`. Render template disables Bolna by default. Set `DATABASE_URL` to managed PostgreSQL, `FRONTEND_URL` to the exact deployed Vercel origin, `COOKIE_SECURE=true`, and `COOKIE_SAMESITE=none` for separate Vercel/Render sites. A custom same-site domain is recommended for browser cookie compatibility.

Set Vercel frontend variable `NEXT_PUBLIC_API_URL` to the Render HTTPS API origin for Production (and to the matching staging API in Preview, if configured). Redeploy Vercel after changing this build-time variable. Redeploy Render after changing `FRONTEND_URL` or other service environment settings. Never put Bolna keys in `NEXT_PUBLIC_*` variables.

The explicit local commands remain `python -m alembic -c alembic.ini upgrade head` then optionally `python seed_database.py`; the Render pre-deploy command runs migrations and does not seed demo listings.

## Earlier implementation summary (2026-10-28)

Continued the existing VoiceDesk project. The root page is the public dashboard, listing search/detail pages are public, and account/voice actions require email/password login. Frontend dependencies, including official `@bolna/web-call` 3.0.1, are now installed and locked. Frontend typecheck, lint, unit tests, production build, API tests, SQLite migration, seed, and local API smoke checks have been run. No real microphone call was initiated.

## Implemented

- Public home dashboard with property search, featured properties, product overview, and AI receptionist CTA; public catalog and property detail.
- Email/password registration and login, validation, password visibility, safe internal `next` redirect, customer-default roles, bcrypt hashes, HttpOnly session cookie, server-side session digest and logout invalidation.
- Protected customer saved homes, bookings, call history, and voice session endpoint. Agent/admin sample endpoints reject customer role.
- Bolna browser SDK integration. Authenticated backend mints sessions using the official Web Call endpoint and server-only bearer key. Browser explicitly starts only on user action. User call-start association and an authenticated personal call-history endpoint are in place.
- `CallRecord` persistence and an idempotent Bolna webhook endpoint store status, duration, and summary only; transcript content is not saved. Configure the webhook and shared secret as described below before summaries can arrive.
- Booking creation uses a required idempotency key, future-time and work-window validation, agent overlap checks, cancellation, and rescheduling. Booking statuses are requests, not claims of external agent/calendar confirmation. PostgreSQL overlap checks use a transaction advisory lock; multi-worker PostgreSQL behavior still needs a live integration test.
- Alembic migration `0002_call_records` and repeatable 30-record fictional listing seed.
- Responsive shared UI and account page with personal call summaries.

## Verification performed

Frontend, from `frontend/`:

- `npm install --offline=false --no-audit --no-fund`: passed; resolved npm registry/dependency issue and generated lockfile.
- `npm run typecheck`: passed (`tsc --noEmit`).
- `npm run lint`: passed (ESLint).
- `npm test`: passed, 9/9 Vitest tests (safe redirect and registration rules).
- `npm run build`: passed on Next.js 15.5.28; routes compiled and static pages generated.

Backend, from `backend/`:

- `python -m pytest -q -p no:cacheprovider`: **7 passed** in the 2026-10-28 audit; the 2026-10-29 production-readiness run passed **16**.
- `python -m alembic -c alembic.ini upgrade head`: passed against local SQLite; current revision `0002_call_records`.
- `python seed_database.py`: ensured 30 demo properties in the earlier audit. This is now an explicit standalone command and is guarded in production.
- `python -m py_compile app.py seed_database.py create_user.py alembic/env.py alembic/versions/0001_initial_schema.py alembic/versions/0002_call_records.py`: passed.
- Local production Next server returned HTTP 200 with the dashboard headline. Local Uvicorn returned health `ok`, 30 public properties, and 401 for unauthenticated private call history.
- Responsive behavior was checked by reviewing the existing 850px/550px CSS breakpoints; no real browser device emulation/visual inspection was available.

One sandboxed Vitest run failed because Node could not spawn esbuild (`EPERM`); the same frontend suite was rerun with permitted process execution and passed. App imports no longer create tables or seed records.

## Bolna integration and credential status

Reviewed the [official Web Call SDK](https://github.com/bolna-ai/web-call), [API authentication](https://www.bolna.ai/docs/api-reference/introduction), and [post-call webhook docs](https://www.bolna.ai/docs/post-call/polling-call-status-webhooks). The implementation follows the documented server-side `POST https://api.bolna.ai/web-call/freeswitch-session` flow; the master API key is not included in frontend bundles or responses. Short-lived session credentials are returned only to the authenticated browser that requested them.

As of this audit, `BOLNA_API_KEY` and `BOLNA_AGENT_ID` are both set in the local ignored environment. A read-only official Bolna agent lookup returned HTTP 200 and confirmed the key is accepted and the configured agent is accessible. No values were printed. This check does not prove the agent's Web Call configuration, browser permissions, or audio. **No real call was started or claimed.** Rotate the key before live demonstration because prior project context flagged it as potentially exposed, then repeat the safe validity check.

To persist final summaries, configure an externally reachable HTTPS webhook URL in the Bolna agent settings and configure a long random `BOLNA_WEBHOOK_SECRET` in backend env and the matching custom webhook header `X-VoiceDesk-Webhook-Secret`. The code rejects requests without the secret and ignores executions that were not associated with an authenticated user's minted session.

## Integrations and remaining blockers

- **Google Calendar:** not implemented beyond config status and explicit demo calendar labeling. No OAuth consent, token storage, free/busy lookup, event creation, cancellation synchronization, or calendar credentials are present. To enable it, register a Google Cloud OAuth client, authorize Calendar API scopes, complete a secure OAuth/token-storage flow, then test a real calendar. No authorization was performed.
- **Email and password reset:** no provider send workflow or reset-token completion exists. Password-reset API returns a clear setup error when email configuration is absent and a not-enabled response when only the old API-key flag is set. No email was sent. A transactional provider account, verified sender/domain, and securely stored API key are required, followed by implementation/testing of expiring one-time reset tokens.
- **Voice summary webhook:** code is ready; provider webhook configuration and external secret setup are still required. Summary delivery was not externally tested.
- **Staff workspaces:** agent lead endpoint is an empty role-protected placeholder; administrator analytics has basic counts, but full agency user/property management and assignment screens remain incomplete.
- **Database concurrency:** PostgreSQL advisory locking serializes appointment overlap checks, but no live multi-worker Postgres run was possible here.
- **CSRF and cookies:** unsafe requests validate Origin and production rejects missing Origin; cookie cross-site browser behavior between Vercel and Render still needs testing. Same-site custom domains are recommended.
- **Distributed rate limits, PostgreSQL connectivity/migration verification, and full browser/responsive visual coverage** remain.

## Exact local start commands (PowerShell)

Backend terminal:

```powershell
cd D:\voicedesk\backend
python -m alembic -c alembic.ini upgrade head
python seed_database.py
python -m uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Frontend terminal:

```powershell
cd D:\voicedesk\frontend
npm run dev
```

Browse to `http://localhost:3000`; check `http://localhost:8000/api/health` for API status.

## Changelog

- 2026-10-29: prepared Render/Vercel production configuration; removed app import-time schema/seed effects; enforced PostgreSQL and secure cookie settings in production; aligned Alembic URL handling; capped DB pools; added Origin checking, database health, production API URL validation, useful API outage messages, safe separate demo seeding, request-status semantics, and production config/webhook/API tests. Backend 16/16, frontend typecheck/lint/build passed, frontend Vitest 9/9. The Bolna endpoint test stubs the provider transport; no external request or real call was made. No service was deployed.
- 2026-10-28: installed/locked frontend dependencies and official Bolna SDK; completed frontend check suite; verified Bolna key and agent via read-only API lookup; added persisted call records/webhook summary handler and booking reschedule endpoint; advanced Alembic migration; refreshed implementation documentation.
- 2026-10-27: dashboard-first experience, auth/session foundation, property search, customer account, booking workflow, Bolna session route, seed data, and baseline project setup.
