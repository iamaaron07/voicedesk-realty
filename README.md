# VoiceDesk Realty

VoiceDesk Realty is a dashboard-first property discovery and AI voice receptionist application. The home page and property catalog are public. Account features, appointment management, and voice session creation require a customer login and are authorized by the FastAPI backend.

## Stack

- `frontend/`: Next.js 15, React 19, TypeScript, responsive CSS, and the official `@bolna/web-call` SDK.
- `backend/`: FastAPI, SQLAlchemy 2, SQLite locally or PostgreSQL, Alembic, bcrypt sessions, and HTTPX provider calls.
- `backend/seed_database.py`: repeatable seed of 30 fictional Bengaluru listings.

## Start locally (Windows PowerShell)

Use two PowerShell terminals. From the project root, the backend terminal:

```powershell
cd D:\voicedesk\backend
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

Open `http://localhost:3000`. API health check: `http://localhost:8000/api/health`. Copy `backend/.env.example` to `backend/.env` and configure `DATABASE_URL`, `FRONTEND_URL`, and provider credentials as needed. Local SQLite is the default if `DATABASE_URL` is omitted.

## Checks

```powershell
cd D:\voicedesk\frontend
npm run typecheck
npm run lint
npm test
npm run build
cd ..\backend
python -m alembic -c alembic.ini upgrade head
python -m pytest -q -p no:cacheprovider
```

## Authentication and roles

Public registration collects email/password only and always creates a customer. Passwords use bcrypt hashes; sessions use opaque HttpOnly cookies with server-side token digests. Configure `COOKIE_SECURE=true` behind HTTPS. Staff users must be provisioned from a trusted shell: `python create_user.py email@example.com --role agent` or `--role admin`; no registration field can grant a staff role. Public browsing does not require login. Saved listings, bookings, call history, and voice session routes do.

## Bolna voice

The browser uses `@bolna/web-call` and requests a short-lived session from authenticated `POST /api/voice/session`. Only the backend sends `BOLNA_API_KEY` to Bolna. The browser starts the microphone and call only after the user presses the call button. Set `BOLNA_API_KEY`, `BOLNA_AGENT_ID`, and `BOLNA_WEB_CALL_ENABLED=true` in the backend environment. Configure the agent's Bolna webhook URL as `https://YOUR_API/api/integrations/bolna/webhook`, set the same random `BOLNA_WEBHOOK_SECRET` in Bolna's custom webhook headers as `X-VoiceDesk-Webhook-Secret`, and in `backend/.env`. Call summaries are stored without transcripts. See [Bolna Web Call SDK](https://github.com/bolna-ai/web-call) and [Bolna post-call webhooks](https://www.bolna.ai/docs/post-call/polling-call-status-webhooks).

## Current integration boundaries

Booking conflicts, idempotency, cancellation, and rescheduling are checked by the API. Calendar event creation and transactional email delivery are not connected yet; current calendar status is explicitly demo mode. Password reset reports a setup message when email is not configured; a complete reset-token workflow is not implemented. Agent leads and staff admin pages remain limited foundations rather than full workspaces. Do not describe the voice call as browser-tested until a user starts an actual call on an authorized browser with microphone access.

## Environment safety

Keep `backend/.env` out of source control and never place provider secrets in `NEXT_PUBLIC_*` variables. Rotate any previously exposed Bolna key before live use. Production also needs HTTPS, secure cookies, a durable database, distributed rate limiting, and a reviewed privacy/retention policy.
