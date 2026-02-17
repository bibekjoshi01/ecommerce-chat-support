# E-commerce Chat Backend (Step 1: Architecture Baseline)

This folder contains the first implementation phase:
- A layered backend structure in Python (FastAPI + SQLAlchemy)
- Conversation lifecycle domain model and transition rules
- API and realtime boundary stubs for incremental development
- Architecture documents in `docs/architecture`

## Run locally (after installing dependencies)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload
```

## Current scope

Implemented in this phase:
- Base app bootstrap and route registration
- Domain enums and lifecycle state machine
- SQLAlchemy entities for conversations/messages/agents/FAQ
- Lifecycle unit tests

Deferred to next phase:
- Real DB repositories and migrations
- WebSocket event handling
- Full customer and agent APIs
- Queueing and assignment workers
