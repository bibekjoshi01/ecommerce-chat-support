from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import AgentPresence, ConversationStatus
from app.schemas.message import MessageResponse


class AgentResponse(BaseModel):
    id: UUID
    display_name: str
    presence: AgentPresence
    max_active_chats: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RegisterAgentRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=120)
    max_active_chats: int = Field(default=3, ge=1, le=20)
    start_online: bool = True


class SetAgentPresenceRequest(BaseModel):
    presence: AgentPresence


class AgentConversationResponse(BaseModel):
    id: UUID
    customer_session_id: str
    status: ConversationStatus
    assigned_agent_id: UUID | None
    requested_agent_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentConversationListResponse(BaseModel):
    items: list[AgentConversationResponse]


class AgentConversationMessagesResponse(BaseModel):
    conversation: AgentConversationResponse
    messages: list[MessageResponse]


class AgentMessageExchangeResponse(BaseModel):
    conversation: AgentConversationResponse
    message: MessageResponse


class AgentCloseConversationResponse(BaseModel):
    conversation: AgentConversationResponse
    system_message: MessageResponse | None
