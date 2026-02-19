# E-commerce Chat System

This repository now includes:

- Layered Python backend (FastAPI + SQLAlchemy + Alembic)
- Customer bot flow (`automated -> agent -> closed`) with persistent chat history
- Minimal frontend app (`React + TypeScript + RTK Query + Vite`) for customer chat
- Architecture docs in `docs/architecture`

## Why React + RTK Query + Vite for this case

- `React` gives clean component boundaries and long-term maintainability.
- `RTK Query` gives typed API integration, caching, and mutation flows with less custom code.
- `Vite` keeps setup and dev feedback fast while staying production-ready.

This is a strong baseline for a technical lead assignment because it demonstrates:

- clear separation of concerns (API/state/UI layers),
- typed contracts across frontend/backend,
- extension-ready structure for future agent dashboard and real-time events.

## Frontend scope (minimal required)

- Home page with floating support chat launcher (bottom-right widget pattern)
- Start/resume customer conversation by session
- Send free-text customer messages and quick-reply FAQ prompts
- Simulated real support feel with short request/reply delay + typing state
- Router-ready app with `/` (customer), `/agent/login`, and protected `/agent`

## Run locally

### 1) Backend setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
```

### 2) Start infrastructure + backend

```bash
docker compose up -d postgres redis
alembic upgrade head
python run_seed.py
uvicorn app.main:app --reload
```

If you also run a local Postgres service, prefer `POSTGRES_HOST=127.0.0.1` in `.env`.

### 3) Start frontend

```bash
cd web
npm install
npm run dev
```

Frontend runs at `http://127.0.0.1:5173` and proxies `/api` to FastAPI (`http://127.0.0.1:8000`).

## Frontend architecture (minimal, but strong)

```text
web/src
  app/                # store + router shell
  features/chat/
    api/              # RTK Query endpoints for customer chat
    model/            # chat slice + controller hook
    ui/               # customer chat widget
  pages/              # route-level pages
  shared/
    lib/              # session-id utility
    types/            # frontend API/domain contracts
```

## Bot flow endpoints (implemented)

- `GET /api/v1/customer/quick-questions`
- `POST /api/v1/customer/conversations/start`
- `GET /api/v1/customer/conversations/{conversation_id}`
- `GET /api/v1/customer/conversations/{conversation_id}/messages`
- `POST /api/v1/customer/conversations/{conversation_id}/quick-replies/{faq_slug}`
- `POST /api/v1/customer/conversations/{conversation_id}/messages`
- `POST /api/v1/customer/conversations/{conversation_id}/escalate`

Conversation-specific customer endpoints require:

- Header: `X-Customer-Session-Id: <customer_session_id>`

## Agent endpoints (implemented)

- `POST /api/v1/agent/auth/login`
- `POST /api/v1/agent/register`
- `GET /api/v1/agent/me`
- `GET /api/v1/agent/conversations?status=automated|agent|closed`
- `GET /api/v1/agent/conversations/{conversation_id}/messages`
- `POST /api/v1/agent/conversations/{conversation_id}/messages`
- `POST /api/v1/agent/conversations/{conversation_id}/close`

Agent-protected endpoints require:

- Header: `Authorization: Bearer <access_token>`

## Seeded agent accounts (dev)

`python run_seed.py` creates default FAQ entries and these agent logins:

## Realtime websocket endpoint

- `WS /api/v1/realtime/ws`

Query patterns:

- Customer stream: `role=customer&conversation_id=<uuid>&customer_session_id=<session_id>`
- Agent stream: `role=agent&access_token=<access_token>[&conversation_id=<uuid>]`
