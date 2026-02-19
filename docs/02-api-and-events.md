# API and Event Contracts

## REST Endpoints

### Customer APIs

- `GET /api/v1/customer/quick-questions`
- `POST /api/v1/customer/conversations/start`
- `GET /api/v1/customer/conversations/{conversation_id}`
- `GET /api/v1/customer/conversations/{conversation_id}/messages`
- `POST /api/v1/customer/conversations/{conversation_id}/messages`
- `POST /api/v1/customer/conversations/{conversation_id}/quick-replies/{faq_slug}`
- `POST /api/v1/customer/conversations/{conversation_id}/escalate`

Conversation-scoped customer endpoints require:
- `X-Customer-Session-Id: <customer_session_id>`

### Agent APIs

- `POST /api/v1/agent/auth/login`
- `POST /api/v1/agent/register`
- `GET /api/v1/agent/me`
- `POST /api/v1/agent/presence`
- `GET /api/v1/agent/conversations?status=automated|agent|closed`
- `GET /api/v1/agent/conversations/{conversation_id}/messages`
- `POST /api/v1/agent/conversations/{conversation_id}/messages`
- `POST /api/v1/agent/conversations/{conversation_id}/close`

Agent-protected endpoints require:
- `Authorization: Bearer <access_token>`

## WebSocket Endpoint

- `WS /api/v1/realtime/ws`

Customer query:
- `role=customer&conversation_id=<uuid>&customer_session_id=<session_id>`

Agent query:
- `role=agent&access_token=<access_token>[&conversation_id=<uuid>]`

## Realtime Events

Server emits:
- `message.created`
- `conversation.updated`
- `agent.assigned`
- `chat.closed`
- `agent.presence.changed`
- `agent.typing`

System/control events:
- `system.connected`
- `system.subscribed`
- `system.unsubscribed`
- `system.error`

## Idempotency and UX Guarantees

- Escalation is idempotent after assignment:
  repeated "Talk to agent" does not duplicate assignment or connection system messages.
- In `AGENT` mode, customer messages are accepted even if the assigned agent is temporarily offline.
- Realtime reconnect on customer side triggers server resync of conversation/messages.

## Error Semantics

- `400 BAD REQUEST` for validation failures.
- `401 UNAUTHORIZED` for invalid/expired agent token.
- `403 FORBIDDEN` for customer-session or agent access violations.
- `404 NOT FOUND` for missing conversation/faq/agent.
- `409 CONFLICT` for invalid state/mode transitions or unavailable-agent escalation.
