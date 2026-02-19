from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import ConversationStatus
from app.schemas.message import MessageResponse


class QuickQuestionResponse(BaseModel):
    slug: str
    question: str


class StartConversationRequest(BaseModel):
    customer_session_id: str | None = Field(default=None, min_length=8, max_length=120)
    force_new: bool = False


class ConversationResponse(BaseModel):
    id: UUID
    customer_session_id: str
    status: ConversationStatus
    assigned_agent_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationBootstrapResponse(BaseModel):
    conversation: ConversationResponse
    quick_questions: list[QuickQuestionResponse]
    messages: list[MessageResponse]
    show_talk_to_agent: bool


class CustomerTextMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class ConversationMessagesResponse(BaseModel):
    conversation: ConversationResponse
    messages: list[MessageResponse]


class BotExchangeResponse(BaseModel):
    conversation: ConversationResponse
    customer_message: MessageResponse
    bot_message: MessageResponse | None
    quick_questions: list[QuickQuestionResponse]
    show_talk_to_agent: bool
