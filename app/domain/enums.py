from enum import Enum


class ConversationStatus(str, Enum):
    AUTOMATED = "automated"
    AGENT = "agent"
    CLOSED = "closed"


class MessageSenderType(str, Enum):
    CUSTOMER = "customer"
    BOT = "bot"
    AGENT = "agent"
    SYSTEM = "system"


class MessageKind(str, Enum):
    TEXT = "text"
    QUICK_REPLY = "quick_reply"
    EVENT = "event"


class AgentPresence(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"


class TransitionAction(str, Enum):
    ESCALATE_TO_AGENT = "escalate_to_agent"
    CLOSE_BY_AGENT = "close_by_agent"
