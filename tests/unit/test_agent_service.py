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
from app.services.agent_service import AgentService
from app.services.errors import (
    AgentConversationAccessDeniedError,
    AgentConversationModeError,
)


class DummySession:
    async def commit(self) -> None:
        return None

    async def refresh(self, _: object) -> None:
        return None


@dataclass(slots=True)
class FakeAgent:
    id: UUID
    display_name: str
    presence: AgentPresence
    max_active_chats: int
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


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


class FakeAgentRepository:
    def __init__(self) -> None:
        self.agents: dict[UUID, FakeAgent] = {}

    async def get_by_id(self, agent_id: UUID) -> FakeAgent | None:
        return self.agents.get(agent_id)

    async def create(
        self,
        display_name: str = "Support Agent",
        max_active_chats: int = 5,
        presence: AgentPresence = AgentPresence.ONLINE,
    ) -> FakeAgent:
        agent = FakeAgent(
            id=uuid4(),
            display_name=display_name,
            presence=presence,
            max_active_chats=max_active_chats,
        )
        self.agents[agent.id] = agent
        return agent

    async def update_presence(self, agent: FakeAgent, presence: AgentPresence) -> None:
        agent.presence = presence
        agent.updated_at = datetime.now(UTC)


class FakeConversationRepository:
    def __init__(self) -> None:
        self.conversations: dict[UUID, FakeConversation] = {}

    async def get_by_id(self, conversation_id: UUID) -> FakeConversation | None:
        return self.conversations.get(conversation_id)

    async def list_for_agent_workspace(
        self,
        agent_id: UUID,
        status_filter: ConversationStatus | None = None,
        limit: int = 100,
    ) -> list[FakeConversation]:
        candidates = [
            conversation
            for conversation in self.conversations.values()
            if conversation.assigned_agent_id == agent_id
            or (
                conversation.status == ConversationStatus.AGENT
                and conversation.assigned_agent_id is None
            )
        ]
        if status_filter is not None:
            candidates = [
                conversation
                for conversation in candidates
                if conversation.status == status_filter
            ]
        ordered = sorted(
            candidates,
            key=lambda conversation: conversation.updated_at,
            reverse=True,
        )
        return ordered[:limit]

    async def assign_agent(self, conversation: FakeConversation, agent_id: UUID) -> None:
        conversation.assigned_agent_id = agent_id
        conversation.requested_agent_at = conversation.requested_agent_at or datetime.now(
            UTC
        )

    async def touch(self, conversation: FakeConversation) -> None:
        conversation.updated_at = datetime.now(UTC)


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


@dataclass(slots=True)
class FixtureState:
    service: AgentService
    primary_agent: FakeAgent
    secondary_agent: FakeAgent
    assigned_conversation: FakeConversation
    unassigned_agent_conversation: FakeConversation
    automated_conversation: FakeConversation


@pytest.fixture
def fixture_state() -> FixtureState:
    session = DummySession()
    agents = FakeAgentRepository()
    conversations = FakeConversationRepository()
    messages = FakeMessageRepository()

    primary_agent = FakeAgent(
        id=uuid4(),
        display_name="Maya",
        presence=AgentPresence.ONLINE,
        max_active_chats=3,
    )
    secondary_agent = FakeAgent(
        id=uuid4(),
        display_name="Alex",
        presence=AgentPresence.ONLINE,
        max_active_chats=3,
    )
    agents.agents[primary_agent.id] = primary_agent
    agents.agents[secondary_agent.id] = secondary_agent

    assigned_conversation = FakeConversation(
        id=uuid4(),
        customer_session_id="session-assigned-1",
        status=ConversationStatus.AGENT,
        assigned_agent_id=primary_agent.id,
    )
    unassigned_agent_conversation = FakeConversation(
        id=uuid4(),
        customer_session_id="session-queue-1",
        status=ConversationStatus.AGENT,
        assigned_agent_id=None,
    )
    automated_conversation = FakeConversation(
        id=uuid4(),
        customer_session_id="session-auto-1",
        status=ConversationStatus.AUTOMATED,
        assigned_agent_id=None,
    )
    conversations.conversations[assigned_conversation.id] = assigned_conversation
    conversations.conversations[unassigned_agent_conversation.id] = (
        unassigned_agent_conversation
    )
    conversations.conversations[automated_conversation.id] = automated_conversation

    service = AgentService(
        session=session,
        agents=agents,
        conversations=conversations,
        messages=messages,
    )
    return FixtureState(
        service=service,
        primary_agent=primary_agent,
        secondary_agent=secondary_agent,
        assigned_conversation=assigned_conversation,
        unassigned_agent_conversation=unassigned_agent_conversation,
        automated_conversation=automated_conversation,
    )


@pytest.mark.asyncio
async def test_register_agent_starts_online(fixture_state: FixtureState) -> None:
    created = await fixture_state.service.register_agent(
        display_name="Jordan",
        max_active_chats=4,
        start_online=True,
    )

    assert created.display_name == "Jordan"
    assert created.presence == AgentPresence.ONLINE
    assert created.max_active_chats == 4


@pytest.mark.asyncio
async def test_list_conversations_filters_for_agent(
    fixture_state: FixtureState,
) -> None:
    conversations = await fixture_state.service.list_conversations(
        agent_id=fixture_state.primary_agent.id,
        status_filter=ConversationStatus.AGENT,
    )

    ids = {conversation.id for conversation in conversations}
    assert fixture_state.assigned_conversation.id in ids
    assert fixture_state.unassigned_agent_conversation.id in ids
    assert fixture_state.automated_conversation.id not in ids


@pytest.mark.asyncio
async def test_send_agent_message_assigns_unassigned_conversation(
    fixture_state: FixtureState,
) -> None:
    result = await fixture_state.service.send_agent_message(
        agent_id=fixture_state.primary_agent.id,
        conversation_id=fixture_state.unassigned_agent_conversation.id,
        content="I can help you with this order.",
    )

    assert result.conversation.assigned_agent_id == fixture_state.primary_agent.id
    assert result.message.sender_type == MessageSenderType.AGENT
    assert result.message.sender_agent_id == fixture_state.primary_agent.id


@pytest.mark.asyncio
async def test_send_agent_message_rejects_other_assigned_agent(
    fixture_state: FixtureState,
) -> None:
    with pytest.raises(AgentConversationAccessDeniedError):
        await fixture_state.service.send_agent_message(
            agent_id=fixture_state.secondary_agent.id,
            conversation_id=fixture_state.assigned_conversation.id,
            content="I should not be able to post here.",
        )


@pytest.mark.asyncio
async def test_close_conversation_moves_state_and_creates_system_message(
    fixture_state: FixtureState,
) -> None:
    result = await fixture_state.service.close_conversation(
        agent_id=fixture_state.primary_agent.id,
        conversation_id=fixture_state.assigned_conversation.id,
    )

    assert result.conversation.status == ConversationStatus.CLOSED
    assert result.conversation.closed_at is not None
    assert result.system_message is not None
    assert result.system_message.sender_type == MessageSenderType.SYSTEM
    assert result.system_message.kind == MessageKind.EVENT


@pytest.mark.asyncio
async def test_close_conversation_rejects_automated_state(
    fixture_state: FixtureState,
) -> None:
    with pytest.raises(AgentConversationModeError):
        await fixture_state.service.close_conversation(
            agent_id=fixture_state.primary_agent.id,
            conversation_id=fixture_state.automated_conversation.id,
        )


@pytest.mark.asyncio
async def test_set_presence_updates_agent_presence(fixture_state: FixtureState) -> None:
    updated = await fixture_state.service.set_presence(
        agent_id=fixture_state.primary_agent.id,
        presence=AgentPresence.OFFLINE,
    )

    assert updated.presence == AgentPresence.OFFLINE
