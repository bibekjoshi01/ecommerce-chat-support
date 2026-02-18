# E-commerce Chat Backend

This repository currently includes:
- Layered Python backend (FastAPI + SQLAlchemy)
- Conversation lifecycle model (`automated -> agent -> closed`)
- Working customer bot flow with persistent conversation history
- Architecture documents in `docs/architecture`

## Run locally (after installing dependencies)

### Shared setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
```

### Option A: Docker Postgres + Docker Redis

```bash
docker compose up -d postgres redis
alembic upgrade head
uvicorn app.main:app --reload
```

### Option B: Local Postgres + local/Docker Redis

Set DB URL in `.env`:

```bash
# .env
DATABASE_URL=postgresql+asyncpg://<user>:<password>@localhost:5432/<db_name>
# (DATABASE_URL_OVERRIDE works too)
```

Then run:

```bash
docker compose up -d redis
alembic upgrade head
uvicorn app.main:app --reload
```

## Bot flow endpoints (implemented)

- `GET /api/v1/customer/quick-questions`
- `POST /api/v1/customer/conversations/start`
- `GET /api/v1/customer/conversations/{conversation_id}`
- `GET /api/v1/customer/conversations/{conversation_id}/messages`
- `POST /api/v1/customer/conversations/{conversation_id}/quick-replies/{faq_slug}`
- `POST /api/v1/customer/conversations/{conversation_id}/messages`

Conversation-specific customer endpoints require:
- Header: `X-Customer-Session-Id: <customer_session_id>`

## Current scope

Implemented:
- Alembic migration baseline (`alembic upgrade head`)
- Default FAQ seeding at startup (after schema exists)
- Bot quick-question replies sourced from database FAQ entries
- Session-based active conversation restore on repeated start requests
- Session ownership checks for conversation reads/writes
- Customer message + bot reply persistence in message history
- Lifecycle unit tests

Deferred:
- Agent assignment and live agent dashboard behavior
- WebSocket event handling
- Queueing/retry workers
