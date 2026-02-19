from enum import StrEnum


class RealtimeEvent(StrEnum):
    MESSAGE_CREATED = "message.created"
    CONVERSATION_UPDATED = "conversation.updated"
    AGENT_ASSIGNED = "agent.assigned"
    CHAT_CLOSED = "chat.closed"
    AGENT_PRESENCE_CHANGED = "agent.presence.changed"
    AGENT_TYPING = "agent.typing"
