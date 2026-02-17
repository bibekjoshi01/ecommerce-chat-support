from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.utils.conversation_service import ConversationService
from app.domain.enums import ConversationStatus, MessageKind, MessageSenderType


class DummySession:
    async def commit(self) -> None:
        return None

    async def refresh(self, _: object) -> None:
        return None


@dataclass(slots=True)
class FakeConversation:
    id: UUID
    customer_session_id: str
    status: ConversationStatus
    assigned_agent_id: UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class FakeMessage:
    id: UUID
    conversation_id: UUID
    sender_type: MessageSenderType
    kind: MessageKind
    content: str
    metadata_json: dict | None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class FakeFaq:
    slug: str
    question: str
    answer: str
    display_order: int
    is_active: bool = True


class FakeConversationRepository:
    def __init__(self) -> None:
        self.conversations: dict[UUID, FakeConversation] = {}

    async def get_by_id(self, conversation_id: UUID) -> FakeConversation | None:
        return self.conversations.get(conversation_id)

    async def get_latest_active_by_session(self, customer_session_id: str) -> FakeConversation | None:
        active = [
            conv
            for conv in self.conversations.values()
            if conv.customer_session_id == customer_session_id and conv.status != ConversationStatus.CLOSED
        ]
        if not active:
            return None
        return sorted(active, key=lambda conv: conv.updated_at, reverse=True)[0]

    async def create(self, customer_session_id: str) -> FakeConversation:
        conv = FakeConversation(
            id=uuid4(),
            customer_session_id=customer_session_id,
            status=ConversationStatus.AUTOMATED,
        )
        self.conversations[conv.id] = conv
        return conv

    async def touch(self, conversation: FakeConversation) -> None:
        conversation.updated_at = datetime.now(timezone.utc)


class FakeMessageRepository:
    def __init__(self) -> None:
        self.messages: list[FakeMessage] = []

    async def create(
        self,
        conversation_id: UUID,
        sender_type: MessageSenderType,
        kind: MessageKind,
        content: str,
        metadata_json: dict | None = None,
        sender_agent_id: UUID | None = None,
    ) -> FakeMessage:
        _ = sender_agent_id
        message = FakeMessage(
            id=uuid4(),
            conversation_id=conversation_id,
            sender_type=sender_type,
            kind=kind,
            content=content,
            metadata_json=metadata_json,
        )
        self.messages.append(message)
        return message

    async def list_by_conversation(self, conversation_id: UUID) -> list[FakeMessage]:
        return [message for message in self.messages if message.conversation_id == conversation_id]


class FakeFaqRepository:
    def __init__(self) -> None:
        self.entries = [
            FakeFaq(
                slug="delivery-date",
                question="What is the delivery date?",
                answer="Most orders are delivered in 3-5 business days.",
                display_order=1,
            ),
            FakeFaq(
                slug="return-policy",
                question="What is the return policy?",
                answer="You can return unused items within 30 days.",
                display_order=2,
            ),
            FakeFaq(
                slug="order-status",
                question="Where is my order?",
                answer="Share your order ID and I can check status.",
                display_order=3,
            ),
        ]

    async def list_active(self) -> list[FakeFaq]:
        return sorted([entry for entry in self.entries if entry.is_active], key=lambda item: item.display_order)

    async def get_active_by_slug(self, faq_slug: str) -> FakeFaq | None:
        for entry in self.entries:
            if entry.is_active and entry.slug == faq_slug:
                return entry
        return None

    async def find_by_question_or_slug(self, user_content: str) -> FakeFaq | None:
        normalized = user_content.strip().lower()
        for entry in self.entries:
            if not entry.is_active:
                continue
            if entry.question.lower() == normalized or entry.slug.lower() == normalized:
                return entry
        return None


@pytest.fixture
def service() -> ConversationService:
    session = DummySession()
    return ConversationService(
        session=session,
        conversations=FakeConversationRepository(),
        messages=FakeMessageRepository(),
        faqs=FakeFaqRepository(),
    )


@pytest.mark.asyncio
async def test_start_conversation_creates_welcome_and_faqs(service: ConversationService) -> None:
    result = await service.start_customer_conversation(customer_session_id="session-abc-123", force_new=False)

    assert result.conversation.customer_session_id == "session-abc-123"
    assert result.show_talk_to_agent is True
    assert len(result.quick_questions) >= 3
    assert len(result.messages) == 1
    assert result.messages[0].sender_type == MessageSenderType.BOT
    assert result.messages[0].kind == MessageKind.EVENT


@pytest.mark.asyncio
async def test_start_conversation_restores_active_session(service: ConversationService) -> None:
    first = await service.start_customer_conversation(customer_session_id="session-restore-1", force_new=False)
    second = await service.start_customer_conversation(customer_session_id="session-restore-1", force_new=False)

    assert first.conversation.id == second.conversation.id
    assert len(second.messages) == 1


@pytest.mark.asyncio
async def test_quick_reply_stores_customer_and_bot_messages(service: ConversationService) -> None:
    bootstrap = await service.start_customer_conversation(customer_session_id="session-quick-1", force_new=False)

    exchange = await service.send_quick_reply(bootstrap.conversation.id, "return-policy")

    assert exchange.customer_message.sender_type == MessageSenderType.CUSTOMER
    assert exchange.customer_message.kind == MessageKind.QUICK_REPLY
    assert exchange.bot_message.sender_type == MessageSenderType.BOT
    assert exchange.bot_message.kind == MessageKind.TEXT
    assert "30 days" in exchange.bot_message.content


@pytest.mark.asyncio
async def test_free_text_returns_fallback_for_unknown_question(service: ConversationService) -> None:
    bootstrap = await service.start_customer_conversation(customer_session_id="session-text-1", force_new=False)

    exchange = await service.send_customer_text_message(
        bootstrap.conversation.id,
        "Can you explain warehouse packing SLA?",
    )

    assert exchange.customer_message.sender_type == MessageSenderType.CUSTOMER
    assert exchange.customer_message.kind == MessageKind.TEXT
    assert exchange.bot_message.sender_type == MessageSenderType.BOT
    assert "Try one of these" in exchange.bot_message.content


@pytest.mark.asyncio
async def test_free_text_matches_faq_question(service: ConversationService) -> None:
    bootstrap = await service.start_customer_conversation(customer_session_id="session-text-2", force_new=False)

    exchange = await service.send_customer_text_message(
        bootstrap.conversation.id,
        "What is the return policy?",
    )

    assert "30 days" in exchange.bot_message.content
    assert exchange.bot_message.metadata_json
    assert exchange.bot_message.metadata_json.get("faq_slug") == "return-policy"
