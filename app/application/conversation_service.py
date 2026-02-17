from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.enums import ConversationStatus


@dataclass(slots=True)
class ConversationSnapshot:
    id: UUID
    customer_session_id: str
    status: ConversationStatus
    assigned_agent_id: UUID | None
    created_at: datetime
    updated_at: datetime


class ConversationService:
    """Use-case orchestrator.

    This class is intentionally minimal in Step 1. In Step 2 we wire repositories,
    agent assignment, message persistence, and realtime fan-out.
    """

    async def start_customer_conversation(self, customer_session_id: str) -> ConversationSnapshot:
        raise NotImplementedError("Implemented in next phase")

    async def escalate_to_agent(self, conversation_id: UUID) -> ConversationSnapshot:
        raise NotImplementedError("Implemented in next phase")

    async def close_conversation(self, conversation_id: UUID, agent_id: UUID) -> ConversationSnapshot:
        raise NotImplementedError("Implemented in next phase")
