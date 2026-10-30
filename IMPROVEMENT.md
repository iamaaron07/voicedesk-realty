# VoiceDesk Realty — implementation status

**Updated:** 2026-10-30
**Current demo target:** existing Next.js frontend on Vercel; FastAPI backend on Render.
**Deployment status:** prepared locally only; no GitHub push or external deployment was performed.

## Changes for the temporary Render demo

- Changed missing/blank `DATABASE_URL` handling so production Render can start with local SQLite rather than failing at import.
- Preserved PostgreSQL URL normalization and the small SQLAlchemy pool when `DATABASE_URL` is supplied.
- Retained SQLite's `check_same_thread=False` connection setting.
- Added idempotent SQLAlchemy table creation to FastAPI's lifespan startup. Importing `app.py` still does not create tables, run migrations, or seed listings.
- Added tests for production SQLite fallback, SQLite connection options, and repeatable table initialization.
- Added `render.yaml` for a free Render web service, with `PORT`, host `0.0.0.0`, exact requested Vercel CORS origin, secure cross-origin cookies, and Bolna disabled.
- Replaced the prior Neon/Vercel-backend deployment directions in `README.md` with Render/Vercel instructions. The frontend source was not changed for this request.

## Runtime and deployment settings

Render commands:

```text
Build: pip install -r requirements.txt
Start: uvicorn app:app --host 0.0.0.0 --port $PORT
Health: /api/health
```

Render demo environment names: `APP_ENV`, `FRONTEND_URL`, `COOKIE_SECURE`, `COOKIE_SAMESITE`, `BOLNA_WEB_CALL_ENABLED`. The Blueprint supplies safe non-secret values. `DATABASE_URL` is optional: leave it unset for SQLite, or configure PostgreSQL in Render. Do not add Bolna credentials while voice is disabled.

Vercel frontend build variable: `NEXT_PUBLIC_API_URL` set to the actual Render HTTPS origin, without `/api`; redeploy the frontend after updating it.

SQLite on Render's free service is ephemeral. A service restart, replacement, or redeploy may erase accounts, bookings, and listings. This is a temporary demo data store. Startup creates schema but does not seed fictional listings. A separate production-protected seed command is documented in `README.md`.

## Validation results

- `cd backend; python -m pytest -q -p no:cacheprovider`: **21 passed**.
- `cd backend; python -m py_compile app.py test_app.py seed_database.py`: passed.
- Parsed `render.yaml` with PyYAML and checked service type `web`, plan `free`, and the literal `$PORT` Uvicorn start command: passed.
- Started Uvicorn locally with `PORT=8765`, bound to `0.0.0.0`, and requested `/api/health`: HTTP 200 with `{"status":"ok","database":"ok"}`.
- `git diff --check`: passed. Git emitted only configured LF/CRLF normalization notices.
- No Render deployment, Vercel redeployment, hosted cookie check, or live PostgreSQL/Bolna integration test was performed.

## External checks still needed

- Configure/deploy the Render Blueprint and confirm its assigned HTTPS hostname.
- Set `NEXT_PUBLIC_API_URL` to that actual hostname in Vercel and redeploy.
- Confirm `/api/health`, public listing calls, login persistence, and CORS against the deployed domains in a browser.
- Render and Vercel use different sites; browser third-party-cookie restrictions may affect session persistence.
- Bolna remains disabled and no live call was tested. Calendar, email delivery, and complete reset-email delivery were not tested or newly implemented.
- PostgreSQL remains supported but was not contacted or required for this temporary deployment.
