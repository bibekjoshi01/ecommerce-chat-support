from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import MessageKind, MessageSenderType


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    sender_type: MessageSenderType
    kind: MessageKind
    content: str
    metadata: dict | None = Field(default=None, alias="metadata_json")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
