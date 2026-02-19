# E-commerce Support Chat System

Implementation for an e-commerce support chat platform.

Implemented flow:

- Customer conversation lifecycle: `automated -> agent -> closed`
- FAQ-backed instant bot replies
- Escalation to human agent
- Agent dashboard (active/closed/all workspace views)
- Realtime updates via WebSocket
- PostgreSQL persistence with Alembic migrations

## Tech Stack

Backend:

- FastAPI
- SQLAlchemy async + asyncpg
- Alembic
- PostgreSQL
- Redis (for realtime/pubsub evolution path)

Frontend:

- React + TypeScript
- Redux Toolkit + RTK Query
- Vite

## Repository Layout

```text
app/                    Backend source
  api/                  REST and websocket routes
  domain/               enums + state machine
  infra/                db models/repos + realtime hub + seeding
  services/             application services
alembic/                DB migrations
tests/                  Unit tests
web/                    Frontend app
docs/architecture/      System and API design notes
```

## Prerequisites

- Python 3.11+
- Node.js 18+
- Docker + Docker Compose (recommended for Postgres/Redis)

## Quick Start (Recommended: Docker Postgres + Redis)

1. Create virtual environment and install backend deps.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

If you use `zsh`, keep the extras quoted exactly: `'.[dev]'`.

2. Configure environment.

```bash
cp .env.example .env
```

3. Start infra and apply migrations.

```bash
docker compose up -d postgres redis
alembic upgrade head
```

4. Seed FAQ + default agent accounts.

```bash
python run_seed.py
```

5. Run backend.

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

6. Run frontend.

```bash
cd web
npm install
npm run dev
```

## Access URLs

- Frontend: `http://127.0.0.1:5173`
- API docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/api/v1/health`
- DB health: `http://127.0.0.1:8000/api/v1/health/db`

## Seeded Agent Accounts (Development)

Created by `python run_seed.py`:

- `bibek.joshi` / `BibekJoshi@123!`
- `john.doe` / `AgentPass123!`
- `admin` / `Admin@123`

## Run Tests

Backend tests:

```bash
./venv/bin/pytest -q
```

Frontend typecheck + production build:

```bash
cd web
npm run build
```

## Local Postgres Instead of Docker (Optional)

If you run PostgreSQL locally, set `.env` accordingly:

- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`

Then run:

```bash
alembic upgrade head
python run_seed.py
uvicorn app.main:app --reload --port 8000
```

## Troubleshooting

`zsh: no matches found: .[dev]`

- Use: `pip install -e '.[dev]'`

`asyncpg.exceptions.InvalidAuthorizationSpecificationError: role "chat_user" does not exist`

- You likely have an old Postgres volume with mismatched credentials.
- Reset local containers/volume and re-run migrations:

```bash
docker compose down -v
docker compose up -d postgres redis
alembic upgrade head
python run_seed.py
```

## Architecture Docs

- `docs/architecture/01-system-architecture.md`
- `docs/architecture/02-api-and-events.md`
- `docs/architecture/03-roadmap.md`
