from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.domain.enums import (
    AgentPresence,
    ConversationStatus,
    MessageKind,
    MessageSenderType,
)
from app.services.conversation_service import ConversationService
from app.services.errors import ConversationAccessDeniedError


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
    requested_agent_at: datetime | None = None
    closed_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class FakeMessage:
    id: UUID
    conversation_id: UUID
    sender_type: MessageSenderType
    kind: MessageKind
    content: str
    metadata_json: dict | None
    sender_agent_id: UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class FakeFaq:
    slug: str
    question: str
    answer: str
    display_order: int
    is_active: bool = True


@dataclass(slots=True)
class FakeAgent:
    id: UUID
    display_name: str
    max_active_chats: int
    presence: AgentPresence = AgentPresence.ONLINE
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class FakeConversationRepository:
    def __init__(self) -> None:
        self.conversations: dict[UUID, FakeConversation] = {}

    async def get_by_id(self, conversation_id: UUID) -> FakeConversation | None:
        return self.conversations.get(conversation_id)

    async def get_by_id_for_update(
        self, conversation_id: UUID
    ) -> FakeConversation | None:
        return self.conversations.get(conversation_id)

    async def get_latest_active_by_session(
        self, customer_session_id: str
    ) -> FakeConversation | None:
        active = [
            conv
            for conv in self.conversations.values()
            if conv.customer_session_id == customer_session_id
            and conv.status != ConversationStatus.CLOSED
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
        conversation.updated_at = datetime.now(UTC)

    async def count_active_assigned_to_agent(self, agent_id: UUID) -> int:
        return len(
            [
                conversation
                for conversation in self.conversations.values()
                if conversation.assigned_agent_id == agent_id
                and conversation.status == ConversationStatus.AGENT
            ]
        )


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
        message = FakeMessage(
            id=uuid4(),
            conversation_id=conversation_id,
            sender_type=sender_type,
            kind=kind,
            content=content,
            metadata_json=metadata_json,
            sender_agent_id=sender_agent_id,
        )
        self.messages.append(message)
        return message

    async def list_by_conversation(self, conversation_id: UUID) -> list[FakeMessage]:
        return [
            message
            for message in self.messages
            if message.conversation_id == conversation_id
        ]


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
        return sorted(
            [entry for entry in self.entries if entry.is_active],
            key=lambda item: item.display_order,
        )

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


class FakeAgentRepository:
    def __init__(self) -> None:
        self.agents: list[FakeAgent] = [
            FakeAgent(
                id=uuid4(),
                display_name="Maya (Agent)",
                max_active_chats=3,
            )
        ]

    async def get_by_id(self, agent_id: UUID) -> FakeAgent | None:
        for agent in self.agents:
            if agent.id == agent_id:
                return agent
        return None

    async def list_online(self) -> list[FakeAgent]:
        return [
            agent for agent in self.agents if agent.presence == AgentPresence.ONLINE
        ]

    async def create(
        self,
        display_name: str = "Support Agent",
        max_active_chats: int = 5,
    ) -> FakeAgent:
        agent = FakeAgent(
            id=uuid4(),
            display_name=display_name,
            max_active_chats=max_active_chats,
        )
        self.agents.append(agent)
        return agent


@pytest.fixture
def service() -> ConversationService:
    session = DummySession()
    return ConversationService(
        session=session,
        conversations=FakeConversationRepository(),
        messages=FakeMessageRepository(),
        faqs=FakeFaqRepository(),
        agents=FakeAgentRepository(),
    )


@pytest.mark.asyncio
async def test_start_conversation_creates_welcome_and_faqs(
    service: ConversationService,
) -> None:
    result = await service.start_customer_conversation(
        customer_session_id="session-abc-123", force_new=False
    )

    assert result.conversation.customer_session_id == "session-abc-123"
    assert result.show_talk_to_agent is True
    assert len(result.quick_questions) >= 3
    assert len(result.messages) == 1
    assert result.messages[0].sender_type == MessageSenderType.BOT
    assert result.messages[0].kind == MessageKind.EVENT


@pytest.mark.asyncio
async def test_start_conversation_restores_active_session(
    service: ConversationService,
) -> None:
    first = await service.start_customer_conversation(
        customer_session_id="session-restore-1", force_new=False
    )
    second = await service.start_customer_conversation(
        customer_session_id="session-restore-1", force_new=False
    )

    assert first.conversation.id == second.conversation.id
    assert len(second.messages) == 1


@pytest.mark.asyncio
async def test_quick_reply_stores_customer_and_bot_messages(
    service: ConversationService,
) -> None:
    bootstrap = await service.start_customer_conversation(
        customer_session_id="session-quick-1", force_new=False
    )

    exchange = await service.send_quick_reply(
        bootstrap.conversation.id,
        "return-policy",
        customer_session_id="session-quick-1",
    )

    assert exchange.customer_message.sender_type == MessageSenderType.CUSTOMER
    assert exchange.customer_message.kind == MessageKind.QUICK_REPLY
    assert exchange.bot_message.sender_type == MessageSenderType.BOT
    assert exchange.bot_message.kind == MessageKind.TEXT
    assert "30 days" in exchange.bot_message.content


@pytest.mark.asyncio
async def test_free_text_returns_fallback_for_unknown_question(
    service: ConversationService,
) -> None:
    bootstrap = await service.start_customer_conversation(
        customer_session_id="session-text-1", force_new=False
    )

    exchange = await service.send_customer_text_message(
        bootstrap.conversation.id,
        "Can you explain warehouse packing SLA?",
        customer_session_id="session-text-1",
    )

    assert exchange.customer_message.sender_type == MessageSenderType.CUSTOMER
    assert exchange.customer_message.kind == MessageKind.TEXT
    assert exchange.bot_message.sender_type == MessageSenderType.BOT
    assert "Try one of these" in exchange.bot_message.content


@pytest.mark.asyncio
async def test_free_text_matches_faq_question(service: ConversationService) -> None:
    bootstrap = await service.start_customer_conversation(
        customer_session_id="session-text-2", force_new=False
    )

    exchange = await service.send_customer_text_message(
        bootstrap.conversation.id,
        "What is the return policy?",
        customer_session_id="session-text-2",
    )

    assert "30 days" in exchange.bot_message.content
    assert exchange.bot_message.metadata_json
    assert exchange.bot_message.metadata_json.get("faq_slug") == "return-policy"


@pytest.mark.asyncio
async def test_free_text_rejects_whitespace_only_content(
    service: ConversationService,
) -> None:
    bootstrap = await service.start_customer_conversation(
        customer_session_id="session-text-empty-1",
        force_new=False,
    )

    with pytest.raises(ValueError, match="cannot be empty"):
        await service.send_customer_text_message(
            bootstrap.conversation.id,
            "   ",
            customer_session_id="session-text-empty-1",
        )


@pytest.mark.asyncio
async def test_get_conversation_fails_for_mismatched_session(
    service: ConversationService,
) -> None:
    bootstrap = await service.start_customer_conversation(
        customer_session_id="session-owner-1",
        force_new=False,
    )

    with pytest.raises(ConversationAccessDeniedError):
        await service.get_conversation(
            bootstrap.conversation.id,
            customer_session_id="session-owner-2",
        )


@pytest.mark.asyncio
async def test_send_message_fails_for_mismatched_session(
    service: ConversationService,
) -> None:
    bootstrap = await service.start_customer_conversation(
        customer_session_id="session-msg-owner-1",
        force_new=False,
    )

    with pytest.raises(ConversationAccessDeniedError):
        await service.send_customer_text_message(
            bootstrap.conversation.id,
            "What is the return policy?",
            customer_session_id="session-msg-owner-2",
        )


@pytest.mark.asyncio
async def test_escalate_to_agent_switches_mode_and_assigns_agent(
    service: ConversationService,
) -> None:
    bootstrap = await service.start_customer_conversation(
        customer_session_id="session-escalate-1",
        force_new=False,
    )

    exchange = await service.escalate_to_agent(
        bootstrap.conversation.id,
        customer_session_id="session-escalate-1",
    )

    assert exchange.conversation.status == ConversationStatus.AGENT
    assert exchange.conversation.assigned_agent_id is not None
    assert exchange.customer_message.sender_type == MessageSenderType.CUSTOMER
    assert exchange.bot_message.sender_type == MessageSenderType.SYSTEM
    assert exchange.show_talk_to_agent is False


@pytest.mark.asyncio
async def test_escalate_to_agent_is_idempotent_after_assignment(
    service: ConversationService,
) -> None:
    bootstrap = await service.start_customer_conversation(
        customer_session_id="session-escalate-repeat-1",
        force_new=False,
    )
    first = await service.escalate_to_agent(
        bootstrap.conversation.id,
        customer_session_id="session-escalate-repeat-1",
    )
    second = await service.escalate_to_agent(
        bootstrap.conversation.id,
        customer_session_id="session-escalate-repeat-1",
    )

    assert second.conversation.status == ConversationStatus.AGENT
    assert second.conversation.assigned_agent_id == first.conversation.assigned_agent_id
    assert second.customer_message.sender_type == MessageSenderType.CUSTOMER
    assert second.bot_message is None

    assert isinstance(service.messages, FakeMessageRepository)
    system_messages = [
        message
        for message in service.messages.messages
        if message.conversation_id == bootstrap.conversation.id
        and message.sender_type == MessageSenderType.SYSTEM
    ]
    assert len(system_messages) == 1


@pytest.mark.asyncio
async def test_send_text_in_agent_mode_queues_message_without_system_reply(
    service: ConversationService,
) -> None:
    bootstrap = await service.start_customer_conversation(
        customer_session_id="session-agent-reply-1",
        force_new=False,
    )
    await service.escalate_to_agent(
        bootstrap.conversation.id,
        customer_session_id="session-agent-reply-1",
    )

    exchange = await service.send_customer_text_message(
        bootstrap.conversation.id,
        "Can you check this order manually?",
        customer_session_id="session-agent-reply-1",
    )

    assert exchange.conversation.status == ConversationStatus.AGENT
    assert exchange.customer_message.sender_type == MessageSenderType.CUSTOMER
    assert exchange.bot_message is None
    assert exchange.show_talk_to_agent is False


@pytest.mark.asyncio
async def test_send_text_in_agent_mode_keeps_assignment_when_agent_offline(
    service: ConversationService,
) -> None:
    bootstrap = await service.start_customer_conversation(
        customer_session_id="session-agent-offline-1",
        force_new=False,
    )
    escalated = await service.escalate_to_agent(
        bootstrap.conversation.id,
        customer_session_id="session-agent-offline-1",
    )
    assigned_agent_id = escalated.conversation.assigned_agent_id
    assert assigned_agent_id is not None

    assert isinstance(service.agents, FakeAgentRepository)
    for agent in service.agents.agents:
        if agent.id == assigned_agent_id:
            agent.presence = AgentPresence.OFFLINE

    exchange = await service.send_customer_text_message(
        bootstrap.conversation.id,
        "I can wait for the assigned agent.",
        customer_session_id="session-agent-offline-1",
    )

    assert exchange.customer_message.sender_type == MessageSenderType.CUSTOMER
    assert exchange.bot_message is None
    assert exchange.conversation.assigned_agent_id == assigned_agent_id


@pytest.mark.asyncio
async def test_send_text_in_agent_mode_succeeds_when_no_agent_available(
    service: ConversationService,
) -> None:
    bootstrap = await service.start_customer_conversation(
        customer_session_id="session-agent-unassigned-1",
        force_new=False,
    )
    await service.escalate_to_agent(
        bootstrap.conversation.id,
        customer_session_id="session-agent-unassigned-1",
    )

    assert isinstance(service.conversations, FakeConversationRepository)
    conversation = service.conversations.conversations[bootstrap.conversation.id]
    conversation.assigned_agent_id = None

    assert isinstance(service.agents, FakeAgentRepository)
    for agent in service.agents.agents:
        agent.presence = AgentPresence.OFFLINE

    exchange = await service.send_customer_text_message(
        bootstrap.conversation.id,
        "I will wait for the next available agent.",
        customer_session_id="session-agent-unassigned-1",
    )

    assert exchange.conversation.status == ConversationStatus.AGENT
    assert exchange.customer_message.sender_type == MessageSenderType.CUSTOMER
    assert exchange.bot_message is None
    assert exchange.conversation.assigned_agent_id is None


@pytest.mark.asyncio
async def test_escalation_prefers_less_loaded_online_agent(
    service: ConversationService,
) -> None:
    assert isinstance(service.agents, FakeAgentRepository)
    assert isinstance(service.conversations, FakeConversationRepository)

    primary_agent = service.agents.agents[0]
    secondary_agent = await service.agents.create(
        display_name="Noah (Agent)",
        max_active_chats=3,
    )

    for index in range(primary_agent.max_active_chats):
        seeded_id = uuid4()
        service.conversations.conversations[seeded_id] = FakeConversation(
            id=seeded_id,
            customer_session_id=f"session-busy-primary-{index}",
            status=ConversationStatus.AGENT,
            assigned_agent_id=primary_agent.id,
        )

    bootstrap = await service.start_customer_conversation(
        customer_session_id="session-load-balance-1",
        force_new=False,
    )
    exchange = await service.escalate_to_agent(
        bootstrap.conversation.id,
        customer_session_id="session-load-balance-1",
    )

    assert exchange.conversation.status == ConversationStatus.AGENT
    assert exchange.conversation.assigned_agent_id == secondary_agent.id


@pytest.mark.asyncio
async def test_escalation_moves_to_waiting_queue_when_no_agent_available(
    service: ConversationService,
) -> None:
    bootstrap = await service.start_customer_conversation(
        customer_session_id="session-queue-no-agent-1",
        force_new=False,
    )

    assert isinstance(service.agents, FakeAgentRepository)
    for agent in service.agents.agents:
        agent.presence = AgentPresence.OFFLINE

    exchange = await service.escalate_to_agent(
        bootstrap.conversation.id,
        customer_session_id="session-queue-no-agent-1",
    )

    assert exchange.conversation.status == ConversationStatus.AGENT
    assert exchange.conversation.assigned_agent_id is None
    assert exchange.show_talk_to_agent is False
    assert exchange.bot_message is not None
    assert exchange.bot_message.sender_type == MessageSenderType.SYSTEM
    assert "queue" in exchange.bot_message.content.lower()


@pytest.mark.asyncio
async def test_queued_escalation_remains_idempotent_for_system_message(
    service: ConversationService,
) -> None:
    bootstrap = await service.start_customer_conversation(
        customer_session_id="session-queue-repeat-1",
        force_new=False,
    )

    assert isinstance(service.agents, FakeAgentRepository)
    for agent in service.agents.agents:
        agent.presence = AgentPresence.OFFLINE

    first = await service.escalate_to_agent(
        bootstrap.conversation.id,
        customer_session_id="session-queue-repeat-1",
    )
    second = await service.escalate_to_agent(
        bootstrap.conversation.id,
        customer_session_id="session-queue-repeat-1",
    )

    assert first.conversation.status == ConversationStatus.AGENT
    assert first.conversation.assigned_agent_id is None
    assert second.conversation.status == ConversationStatus.AGENT
    assert second.conversation.assigned_agent_id is None
    assert second.bot_message is None

    assert isinstance(service.messages, FakeMessageRepository)
    queue_system_messages = [
        message
        for message in service.messages.messages
        if message.conversation_id == bootstrap.conversation.id
        and message.sender_type == MessageSenderType.SYSTEM
        and "queue" in message.content.lower()
    ]
    assert len(queue_system_messages) == 1
