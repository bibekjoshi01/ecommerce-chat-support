from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.domain.enums import ConversationStatus


class StartConversationRequest(BaseModel):
    customer_session_id: str


class ConversationResponse(BaseModel):
    id: UUID
    customer_session_id: str
    status: ConversationStatus
    assigned_agent_id: UUID | None
    created_at: datetime
    updated_at: datetime


class EscalateConversationResponse(BaseModel):
    conversation_id: UUID
    status: ConversationStatus
    assigned_agent_id: UUID | None
    message: str
