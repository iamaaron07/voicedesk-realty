# VoiceDesk Realty — implementation and verification status

**Updated:** 2026-10-28

## Summary

Continued the existing VoiceDesk project. The root page is the public dashboard, listing search/detail pages are public, and account/voice actions require email/password login. Frontend dependencies, including official `@bolna/web-call` 3.0.1, are now installed and locked. Frontend typecheck, lint, unit tests, production build, API tests, SQLite migration, seed, and local API smoke checks have been run. No real microphone call was initiated.

## Implemented

- Public home dashboard with property search, featured properties, product overview, and AI receptionist CTA; public catalog and property detail.
- Email/password registration and login, validation, password visibility, safe internal `next` redirect, customer-default roles, bcrypt hashes, HttpOnly session cookie, server-side session digest and logout invalidation.
- Protected customer saved homes, bookings, call history, and voice session endpoint. Agent/admin sample endpoints reject customer role.
- Bolna browser SDK integration. Authenticated backend mints sessions using the official Web Call endpoint and server-only bearer key. Browser explicitly starts only on user action. User call-start association and an authenticated personal call-history endpoint are in place.
- `CallRecord` persistence and an idempotent Bolna webhook endpoint store status, duration, and summary only; transcript content is not saved. Configure the webhook and shared secret as described below before summaries can arrive.
- Booking creation uses a required idempotency key, future-time and work-window validation, agent overlap checks, cancellation, and rescheduling. The overlap query prevents sequential double booking. Concurrent multi-worker race prevention is not proven and should be added before high-volume production use.
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

- `python -m pytest -q -p no:cacheprovider`: **7 passed**, including booking reschedule and timezone serialization.
- `python -m alembic -c alembic.ini upgrade head`: passed against local SQLite; current revision `0002_call_records`.
- `python seed_database.py`: ensured 30 demo properties.
- `python -m py_compile app.py seed_database.py create_user.py alembic/env.py alembic/versions/0001_initial_schema.py alembic/versions/0002_call_records.py`: passed.
- Local production Next server returned HTTP 200 with the dashboard headline. Local Uvicorn returned health `ok`, 30 public properties, and 401 for unauthenticated private call history.
- Responsive behavior was checked by reviewing the existing 850px/550px CSS breakpoints; no real browser device emulation/visual inspection was available.

One sandboxed Vitest run failed because Node could not spawn esbuild (`EPERM`); the same frontend suite was rerun with the permitted elevated process execution and passed. The initial migration attempt also found `call_records` already created by app import; migration 0002 now detects the table and is idempotent with that existing bootstrap behavior.

## Bolna integration and credential status

Reviewed the [official Web Call SDK](https://github.com/bolna-ai/web-call), [API authentication](https://www.bolna.ai/docs/api-reference/introduction), and [post-call webhook docs](https://www.bolna.ai/docs/post-call/polling-call-status-webhooks). The implementation follows the documented server-side `POST https://api.bolna.ai/web-call/freeswitch-session` flow; the master API key is not included in frontend bundles or responses. Short-lived session credentials are returned only to the authenticated browser that requested them.

As of this audit, `BOLNA_API_KEY` and `BOLNA_AGENT_ID` are both set in the local ignored environment. A read-only official Bolna agent lookup returned HTTP 200 and confirmed the key is accepted and the configured agent is accessible. No values were printed. This check does not prove the agent's Web Call configuration, browser permissions, or audio. **No real call was started or claimed.** Rotate the key before live demonstration because prior project context flagged it as potentially exposed, then repeat the safe validity check.

To persist final summaries, configure an externally reachable HTTPS webhook URL in the Bolna agent settings and configure a long random `BOLNA_WEBHOOK_SECRET` in backend env and the matching custom webhook header `X-VoiceDesk-Webhook-Secret`. The code rejects requests without the secret and ignores executions that were not associated with an authenticated user's minted session.

## Integrations and remaining blockers

- **Google Calendar:** not implemented beyond config status and explicit demo calendar labeling. No OAuth consent, token storage, free/busy lookup, event creation, cancellation synchronization, or calendar credentials are present. To enable it, register a Google Cloud OAuth client, authorize Calendar API scopes, complete a secure OAuth/token-storage flow, then test a real calendar. No authorization was performed.
- **Email and password reset:** no provider send workflow or reset-token completion exists. Password-reset API returns a clear setup error when email configuration is absent and a not-enabled response when only the old API-key flag is set. No email was sent. A transactional provider account, verified sender/domain, and securely stored API key are required, followed by implementation/testing of expiring one-time reset tokens.
- **Voice summary webhook:** code is ready; provider webhook configuration and external secret setup are still required. Summary delivery was not externally tested.
- **Staff workspaces:** agent lead endpoint is an empty role-protected placeholder; administrator analytics has basic counts, but full agency user/property management and assignment screens remain incomplete.
- **Database concurrency:** conflict validation is effective for sequential requests, but two concurrent workers can still race without a database-level exclusion/locking strategy.
- **Password reset, CSRF hardening for cross-site production hosting, distributed rate limits, PostgreSQL migration verification, and full browser/responsive visual coverage** remain.

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

- 2026-10-28: installed/locked frontend dependencies and official Bolna SDK; completed frontend check suite; verified Bolna key and agent via read-only API lookup; added persisted call records/webhook summary handler and booking reschedule endpoint; advanced Alembic migration; refreshed implementation documentation.
- 2026-10-27: dashboard-first experience, auth/session foundation, property search, customer account, booking workflow, Bolna session route, seed data, and baseline project setup.
