# E-commerce Chat Backend

This repository currently includes:
- Layered Python backend (FastAPI + SQLAlchemy)
- Conversation lifecycle model (`automated -> agent -> closed`)
- Working customer bot flow with persistent conversation history
- Architecture documents in `docs/architecture`

## Run locally (after installing dependencies)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
docker compose up -d postgres redis
uvicorn app.main:app --reload
```

## Bot flow endpoints (implemented)

- `GET /api/v1/customer/quick-questions`
- `POST /api/v1/customer/conversations/start`
- `GET /api/v1/customer/conversations/{conversation_id}`
- `GET /api/v1/customer/conversations/{conversation_id}/messages`
- `POST /api/v1/customer/conversations/{conversation_id}/quick-replies/{faq_slug}`
- `POST /api/v1/customer/conversations/{conversation_id}/messages`

## Current scope

Implemented:
- DB bootstrap (`create_all`) and default FAQ seeding for local startup
- Bot quick-question replies sourced from database FAQ entries
- Session-based active conversation restore on repeated start requests
- Customer message + bot reply persistence in message history
- Lifecycle unit tests

Deferred:
- Agent assignment and live agent dashboard behavior
- WebSocket event handling
- Alembic migrations (currently using startup `create_all` for local dev)
- Queueing/retry workers
