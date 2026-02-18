# API and Event Contracts (Step 1 Draft)

## REST Endpoints

### Customer
Implemented in current phase:
- `GET /api/v1/customer/quick-questions`
- `POST /api/v1/customer/conversations/start`
- `GET /api/v1/customer/conversations/{conversation_id}`
- `GET /api/v1/customer/conversations/{conversation_id}/messages`
- `POST /api/v1/customer/conversations/{conversation_id}/messages`
- `POST /api/v1/customer/conversations/{conversation_id}/quick-replies/{faq_slug}`
- Conversation-scoped endpoints require header:
  - `X-Customer-Session-Id: <customer_session_id>`

Deferred:
- `POST /api/v1/customer/conversations/{conversation_id}/escalate`

### Agent
- `GET /api/v1/agent/conversations?status=automated|agent|closed`
- `POST /api/v1/agent/conversations/{conversation_id}/messages`
- `POST /api/v1/agent/conversations/{conversation_id}/close`
- `POST /api/v1/agent/presence` (online/offline)

## WebSocket/Socket Events

Client subscribe channels:
- `conversation:{conversation_id}`
- `agent:{agent_id}:queue`

Server emits:
- `message.created`
- `conversation.updated`
- `agent.assigned`
- `chat.closed`
- `agent.presence.changed`

## Idempotency Guidance

- `escalate` endpoint accepts optional idempotency key header.
- repeated escalate requests for same conversation should not duplicate assignment.

## Error Semantics

- `409 CONFLICT` for invalid lifecycle transition.
- `423 LOCKED` when concurrent operation holds assignment lock.
- `404` for missing conversation.
- `403 FORBIDDEN` when conversation session ownership check fails.
- `400` for validation failures.
