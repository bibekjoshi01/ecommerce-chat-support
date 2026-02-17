from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.enums import MessageKind, MessageSenderType


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    sender_type: MessageSenderType
    kind: MessageKind
    content: str
    created_at: datetime
