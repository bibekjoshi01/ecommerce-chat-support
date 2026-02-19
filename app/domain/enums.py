from enum import StrEnum


class ConversationStatus(StrEnum):
    AUTOMATED = "automated"
    AGENT = "agent"
    CLOSED = "closed"


class MessageSenderType(StrEnum):
    CUSTOMER = "customer"
    BOT = "bot"
    AGENT = "agent"
    SYSTEM = "system"


class MessageKind(StrEnum):
    TEXT = "text"
    QUICK_REPLY = "quick_reply"
    EVENT = "event"


class AgentPresence(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"


class TransitionAction(StrEnum):
    ESCALATE_TO_AGENT = "escalate_to_agent"
    CLOSE_BY_AGENT = "close_by_agent"
