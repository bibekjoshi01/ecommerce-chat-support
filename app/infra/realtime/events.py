from enum import Enum


class RealtimeEvent(str, Enum):
    MESSAGE_CREATED = "message.created"
    CONVERSATION_UPDATED = "conversation.updated"
    AGENT_ASSIGNED = "agent.assigned"
    CHAT_CLOSED = "chat.closed"
    AGENT_PRESENCE_CHANGED = "agent.presence.changed"
