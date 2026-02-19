from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import (
    AgentPresence,
    ConversationStatus,
    MessageKind,
    MessageSenderType,
)
from app.infra.db.models import Agent, Conversation, FaqEntry, Message


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, conversation_id: UUID) -> Conversation | None:
        return await self.session.get(Conversation, conversation_id)

    async def get_latest_active_by_session(
        self, customer_session_id: str
    ) -> Conversation | None:
        stmt: Select[tuple[Conversation]] = (
            select(Conversation)
            .where(
                Conversation.customer_session_id == customer_session_id,
                Conversation.status != ConversationStatus.CLOSED,
            )
            .order_by(Conversation.updated_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, customer_session_id: str) -> Conversation:
        conversation = Conversation(
            customer_session_id=customer_session_id, status=ConversationStatus.AUTOMATED
        )
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def touch(self, conversation: Conversation) -> None:
        conversation.updated_at = datetime.now(UTC)
        await self.session.flush()

    async def count_active_assigned_to_agent(self, agent_id: UUID) -> int:
        stmt: Select[tuple[int]] = select(func.count(Conversation.id)).where(
            Conversation.assigned_agent_id == agent_id,
            Conversation.status == ConversationStatus.AGENT,
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        conversation_id: UUID,
        sender_type: MessageSenderType,
        kind: MessageKind,
        content: str,
        metadata_json: dict | None = None,
        sender_agent_id: UUID | None = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            sender_type=sender_type,
            sender_agent_id=sender_agent_id,
            kind=kind,
            content=content,
            metadata_json=metadata_json,
        )
        self.session.add(message)
        await self.session.flush()
        await self.session.refresh(message)
        return message

    async def list_by_conversation(self, conversation_id: UUID) -> list[Message]:
        stmt: Select[tuple[Message]] = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class FaqRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active(self) -> list[FaqEntry]:
        stmt: Select[tuple[FaqEntry]] = (
            select(FaqEntry)
            .where(FaqEntry.is_active.is_(True))
            .order_by(FaqEntry.display_order.asc(), FaqEntry.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_by_slug(self, faq_slug: str) -> FaqEntry | None:
        stmt: Select[tuple[FaqEntry]] = (
            select(FaqEntry)
            .where(FaqEntry.slug == faq_slug, FaqEntry.is_active.is_(True))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_question_or_slug(self, user_content: str) -> FaqEntry | None:
        normalized = user_content.strip().lower()
        if not normalized:
            return None

        stmt: Select[tuple[FaqEntry]] = (
            select(FaqEntry)
            .where(
                FaqEntry.is_active.is_(True),
                or_(
                    func.lower(FaqEntry.question) == normalized,
                    func.lower(FaqEntry.slug) == normalized,
                ),
            )
            .order_by(FaqEntry.display_order.asc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class AgentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, agent_id: UUID) -> Agent | None:
        return await self.session.get(Agent, agent_id)

    async def list_online(self) -> list[Agent]:
        stmt: Select[tuple[Agent]] = (
            select(Agent)
            .where(Agent.presence == AgentPresence.ONLINE)
            .order_by(Agent.created_at.asc(), Agent.id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        display_name: str = "Support Agent",
        max_active_chats: int = 5,
        presence: AgentPresence = AgentPresence.ONLINE,
    ) -> Agent:
        agent = Agent(
            display_name=display_name,
            max_active_chats=max_active_chats,
            presence=presence,
        )
        self.session.add(agent)
        await self.session.flush()
        await self.session.refresh(agent)
        return agent
