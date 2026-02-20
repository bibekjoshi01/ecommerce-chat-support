# Assignment Validation Checklist

This checklist maps each assignment requirement to implementation evidence and
verification coverage.

## Functional requirements

| Requirement | Implementation evidence | Verification evidence |
| --- | --- | --- |
| Customer can start chat without authentication | `POST /api/v1/customer/conversations/start` in `app/api/v1/routes/customer.py` | `test_start_conversation_creates_welcome_and_faqs` |
| Each new chat has unique session/conversation | Session bootstrap in `ConversationService.start_customer_conversation` | `test_start_conversation_restores_active_session` (reuses existing) + manual `force_new=true` |
| History persists on refresh for same session | `get_latest_active_by_session` + message fetch endpoints | `test_start_conversation_restores_active_session` + frontend websocket resync logic |
| Conversation starts in bot mode | `ConversationStatus.AUTOMATED` default in models/state machine | `test_automated_to_agent_transition`, `test_talk_to_agent_visibility_rules` |
| Quick questions + instant bot replies | FAQ-backed quick reply flow in `send_quick_reply` | `test_quick_reply_stores_customer_and_bot_messages` |
| FAQ responses configurable from DB | `faq_entries` table + repository in `FaqRepository` | Seeded FAQ data in `app/infra/db/seed.py`; no UI hardcoding |
| “Talk to agent” shown in bot mode | state-derived visibility in backend + UI checks | `test_talk_to_agent_visibility_rules` |
| Escalation to agent mode + assignment + system notice | `ConversationService.escalate_to_agent` | `test_escalate_to_agent_switches_mode_and_assigns_agent` |
| Repeated talk-to-agent clicks are safe | Row lock + idempotent system message logic | `test_escalate_to_agent_is_idempotent_after_assignment`, `test_queued_escalation_remains_idempotent_for_system_message` |
| No agent available handling | Escalation enters waiting queue (`AGENT`, unassigned) | `test_escalation_moves_to_waiting_queue_when_no_agent_available` |
| Agent dashboard sees waiting + active conversations | workspace filtering in `web/src/features/agent/model/useAgentWorkspaceController.ts` | Manual UI verification (`Active`/`Waiting` filters) |
| One agent per conversation | assignment guards in `AgentService` and access checks | `test_send_agent_message_rejects_other_assigned_agent` |
| Agent can end conversation | `POST /agent/conversations/{id}/close` | `test_close_conversation_moves_state_and_creates_system_message` |
| Closed conversation is terminal/read-only | state machine + service guards | `test_closed_is_read_only`, `test_agent_to_closed_transition` |
| New chat after close creates new conversation | `force_new=true` behavior on start endpoint | Manual verification with chat widget “New chat” |

## Edge cases coverage

| Edge case | Coverage |
| --- | --- |
| Multiple “Talk to agent” clicks | Automated tests for assigned and waiting paths |
| No agent available | Waiting queue transition test |
| Agent disconnect during active chat | Customer messages still accepted in agent mode (`test_send_text_in_agent_mode_keeps_assignment_when_agent_offline`) |
| Page refresh during active conversation | Backend restore + frontend sync logic |
| Multiple agents online | Least-loaded assignment test (`test_escalation_prefers_less_loaded_online_agent`) |

## Local verification commands

```bash
./venv/bin/ruff check app tests
./venv/bin/mypy app
./venv/bin/pytest -q
cd web && npm run build
```
