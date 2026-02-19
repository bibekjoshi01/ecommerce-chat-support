# E-commerce Support Chat - System Architecture (Python Stack)

## 1. Goal and Scope

This design targets a production-ready support chat system with:

- instant FAQ bot replies,
- seamless handoff to human agents,
- strict conversation lifecycle correctness (`AUTOMATED -> AGENT -> CLOSED`),
- persistence and refresh resilience,
- clean extensibility for scale.

Current repository status:

- backend and frontend baseline are implemented,
- bot and agent flows are running end-to-end,
- docs describe the architecture used by the current implementation.

## 2. Architectural Style

Use a **modular monolith** first, with boundaries ready for service extraction later.

Why this is the right first step:

- lower operational complexity than microservices,
- faster delivery for interview timeline,
- clear module boundaries (`domain`, `application`, `infra`) that can be split when scale demands.

## 3. High-Level Components

```mermaid
flowchart LR
  CW[Customer Chat Widget<br/>Unauthenticated session]
  AD[Agent Dashboard]

  API[FastAPI App<br/>REST + WebSocket]
  APP[Application Layer<br/>Use-case orchestration]
  DOM[Domain Layer<br/>State machine + rules]
  DB[(PostgreSQL)]
  REDIS[(Redis)]

  CW --> API
  AD --> API

  API --> APP --> DOM
  APP --> DB
  API --> REDIS
```

## 4. Core Domain Model

### Conversation

- `id (UUID)`
- `customer_session_id (string)`
- `status (automated|agent|closed)`
- `assigned_agent_id (nullable UUID)`
- `requested_agent_at (nullable timestamp)`
- `closed_at (nullable timestamp)`
- `created_at`, `updated_at`

### Message

- `id (UUID)`
- `conversation_id (UUID)`
- `sender_type (customer|bot|agent|system)`
- `sender_agent_id (nullable UUID)`
- `kind (text|quick_reply|event)`
- `content (text)`
- `metadata_json (jsonb)`
- `created_at`

### Agent

- `id (UUID)`
- `display_name`
- `presence (online|offline)`
- `max_active_chats`
- `created_at`, `updated_at`

### FAQ Entry

- `slug` (unique)
- `question`
- `answer`
- `display_order`
- `is_active`

## 5. Lifecycle and State Rules

Primary state machine:

- `AUTOMATED -> AGENT -> CLOSED`

Rules:

- new conversation starts in `AUTOMATED`.
- `Talk to agent` moves state to `AGENT` (idempotent on repeated clicks).
- `AGENT` can be:
  - waiting queue (`assigned_agent_id = null`)
  - actively handled (`assigned_agent_id != null`)
- only agent can transition `AGENT -> CLOSED`.
- `CLOSED` is read-only and terminal.

UI contract:

- show `Talk to agent` only in `AUTOMATED` mode.
- hide `Talk to agent` after handoff.

## 6. Realtime Strategy

Transport:

- Socket.IO or WebSocket channel per conversation.

Publish events:

- `message.created`
- `conversation.updated`
- `agent.assigned`
- `chat.closed`
- `agent.presence.changed`

Fallback:

- if socket disconnects, REST polling endpoint remains available for recovery.

## 7. Agent Assignment Strategy

Current strategy:

- assign the least-loaded online agent.
- hard rule: max one assigned agent per conversation.
- if no agent has available capacity, escalation still enters `AGENT` queue mode and
  remains unassigned until an agent picks it up.
- once chat is already in `AGENT` mode, customer messages are still accepted even if agent is temporarily offline.

## 8. Edge Case Handling

- multiple `Talk to agent` clicks:
  - idempotent operation, no duplicate assignment, no duplicate system messages.
- no agent available:
  - escalation enters `AGENT` queue mode with no assignment yet.
- agent disconnects mid-chat:
  - customer can continue sending messages; chat remains in `AGENT` mode and waits for agent reply.
- customer refreshes page:
  - same `customer_session_id` restores active conversation and history.
- multiple agents online:
  - least-loaded online agent gets new escalation.

## 9. Consistency and Concurrency

Use DB transaction boundaries for:

- status transitions,
- agent assignment,
- message insert + conversation `updated_at` update.

Future enhancement for heavy contention:

- `SELECT ... FOR UPDATE SKIP LOCKED` for deterministic assignment locking.

## 10. Security and Guardrails

- anonymous customer access with signed session token/cookie.
- server-side input validation and message length limits.
- optional rate limit for bot-triggered requests per session.
- audit-friendly system messages for key lifecycle events.

## 11. Scalability Path

When load increases:

- split into services (`chat-api`, `realtime-gateway`, `assignment-worker`),
- move event fanout to Redis Pub/Sub or Kafka,
- add read replicas for conversation history,
- preserve same domain contracts and event names.
