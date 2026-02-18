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

### Docker Postgres + Docker Redis

```bash
docker compose up -d postgres redis
alembic upgrade head
uvicorn app.main:app --reload
```

If you also run a local Postgres service, keep `POSTGRES_HOST=localhost` (not `localhost`)
in `.env` to avoid IPv6 `localhost` resolving to the wrong database.

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
