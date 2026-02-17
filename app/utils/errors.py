from uuid import UUID

from app.domain.enums import ConversationStatus


class ConversationNotFoundError(LookupError):
    def __init__(self, conversation_id: UUID) -> None:
        super().__init__(f"Conversation '{conversation_id}' not found")
        self.conversation_id = conversation_id


class ConversationClosedError(ValueError):
    def __init__(self, conversation_id: UUID) -> None:
        super().__init__(f"Conversation '{conversation_id}' is closed and read-only")
        self.conversation_id = conversation_id


class ConversationModeError(ValueError):
    def __init__(self, conversation_id: UUID, status: ConversationStatus) -> None:
        super().__init__(
            f"Conversation '{conversation_id}' is in '{status.value}' mode. Bot actions require automated mode."
        )
        self.conversation_id = conversation_id
        self.status = status


class FaqNotFoundError(LookupError):
    def __init__(self, faq_slug: str) -> None:
        super().__init__(f"FAQ '{faq_slug}' not found or inactive")
        self.faq_slug = faq_slug
