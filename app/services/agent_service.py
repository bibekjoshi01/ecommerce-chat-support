from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import (
    AgentPresence,
    ConversationStatus,
    MessageKind,
    MessageSenderType,
    TransitionAction,
)
from app.domain.state_machine import ConversationLifecycle
from app.infra.db.models import Agent, Conversation, Message
from app.infra.db.repositories import (
    AgentRepository,
    ConversationRepository,
    MessageRepository,
)
from app.infra.realtime.channels import (
    AGENT_PRESENCE_CHANNEL,
    agent_queue_channel,
    conversation_channel,
)
from app.infra.realtime.events import RealtimeEvent
from app.infra.realtime.publisher import NoopRealtimePublisher, RealtimePublisher
from app.services.errors import (
    AgentConversationAccessDeniedError,
    AgentConversationModeError,
    AgentNotFoundError,
    ConversationClosedError,
    ConversationNotFoundError,
)


@dataclass(slots=True)
class AgentConversationMessages:
    conversation: Conversation
    messages: list[Message]


@dataclass(slots=True)
class AgentMessageResult:
    conversation: Conversation
    message: Message


@dataclass(slots=True)
class AgentCloseResult:
    conversation: Conversation
    system_message: Message | None


class AgentService:
    def __init__(
        self,
        session: AsyncSession,
        agents: AgentRepository | None = None,
        conversations: ConversationRepository | None = None,
        messages: MessageRepository | None = None,
        realtime: RealtimePublisher | None = None,
    ) -> None:
        self.session = session
        self.agents = agents or AgentRepository(session)
        self.conversations = conversations or ConversationRepository(session)
        self.messages = messages or MessageRepository(session)
        self.realtime = realtime or NoopRealtimePublisher()

    async def register_agent(
        self,
        display_name: str,
        max_active_chats: int,
        start_online: bool = True,
    ) -> Agent:
        cleaned_display_name = display_name.strip()
        presence = AgentPresence.ONLINE if start_online else AgentPresence.OFFLINE
        agent = await self.agents.create(
            display_name=cleaned_display_name,
            max_active_chats=max_active_chats,
            presence=presence,
        )
        await self.session.commit()
        await self.session.refresh(agent)
        await self._emit_agent_presence_changed(agent)
        return agent

    async def set_presence(self, agent_id: UUID, presence: AgentPresence) -> Agent:
        agent = await self._get_agent_or_raise(agent_id)
        await self.agents.update_presence(agent, presence)
        await self.session.commit()
        await self.session.refresh(agent)
        await self._emit_agent_presence_changed(agent)
        return agent

    async def get_agent(self, agent_id: UUID) -> Agent:
        return await self._get_agent_or_raise(agent_id)

    async def list_conversations(
        self,
        agent_id: UUID,
        status_filter: ConversationStatus | None = None,
    ) -> list[Conversation]:
        await self._get_agent_or_raise(agent_id)
        return await self.conversations.list_for_agent_workspace(
            agent_id=agent_id,
            status_filter=status_filter,
        )

    async def get_conversation_messages(
        self,
        agent_id: UUID,
        conversation_id: UUID,
    ) -> AgentConversationMessages:
        await self._get_agent_or_raise(agent_id)
        conversation = await self._get_conversation_for_agent(
            agent_id,
            conversation_id,
            allow_unassigned=True,
        )
        messages = await self.messages.list_by_conversation(conversation.id)
        return AgentConversationMessages(
            conversation=conversation,
            messages=messages,
        )

    async def send_agent_message(
        self,
        agent_id: UUID,
        conversation_id: UUID,
        content: str,
    ) -> AgentMessageResult:
        agent = await self._get_agent_or_raise(agent_id)
        conversation = await self._get_conversation_for_agent(
            agent_id,
            conversation_id,
            allow_unassigned=True,
        )
        self._assert_agent_mode(conversation)

        assigned_now = False
        if conversation.assigned_agent_id is None:
            # FIXME: Add row-level locking on conversation claim to prevent
            # two agents from claiming the same waiting conversation concurrently.
            # Planned approach: SELECT ... FOR UPDATE (or SKIP LOCKED queue pick).
            await self.conversations.assign_agent(conversation, agent.id)
            assigned_now = True

        cleaned_content = content.strip()
        if not cleaned_content:
            raise ValueError("Message content cannot be empty.")

        message = await self.messages.create(
            conversation_id=conversation.id,
            sender_type=MessageSenderType.AGENT,
            sender_agent_id=agent.id,
            kind=MessageKind.TEXT,
            content=cleaned_content,
            metadata_json={"show_talk_to_agent": False},
        )
        await self.conversations.touch(conversation)

        await self.session.commit()
        await self.session.refresh(conversation)

        await self._emit_message_created(message)
        await self._emit_conversation_updated(conversation)
        if assigned_now:
            await self._emit_agent_assigned(conversation, agent)

        return AgentMessageResult(
            conversation=conversation,
            message=message,
        )

    async def close_conversation(
        self,
        agent_id: UUID,
        conversation_id: UUID,
    ) -> AgentCloseResult:
        agent = await self._get_agent_or_raise(agent_id)
        conversation = await self._get_conversation_for_agent(
            agent_id,
            conversation_id,
            allow_unassigned=True,
        )

        if conversation.status == ConversationStatus.AUTOMATED:
            raise AgentConversationModeError(conversation.id, conversation.status)

        if conversation.status == ConversationStatus.CLOSED:
            return AgentCloseResult(conversation=conversation, system_message=None)

        if conversation.assigned_agent_id is None:
            # FIXME: Same claim-race caveat as send_agent_message().
            # Closing an unassigned AGENT conversation should use a lock-backed claim.
            await self.conversations.assign_agent(conversation, agent.id)

        conversation.status = ConversationLifecycle.transition(
            conversation.status,
            TransitionAction.CLOSE_BY_AGENT,
        )
        conversation.closed_at = datetime.now(UTC)

        system_message = await self.messages.create(
            conversation_id=conversation.id,
            sender_type=MessageSenderType.SYSTEM,
            kind=MessageKind.EVENT,
            content=f"{agent.display_name} closed the chat.",
            metadata_json={"closed_by_agent_id": str(agent.id)},
        )
        await self.conversations.touch(conversation)

        await self.session.commit()
        await self.session.refresh(conversation)

        await self._emit_message_created(system_message)
        await self._emit_conversation_updated(conversation)
        await self._emit_chat_closed(conversation)

        return AgentCloseResult(
            conversation=conversation,
            system_message=system_message,
        )

    async def _get_agent_or_raise(self, agent_id: UUID) -> Agent:
        agent = await self.agents.get_by_id(agent_id)
        if agent is None:
            raise AgentNotFoundError(agent_id)
        return agent

    async def _get_conversation_for_agent(
        self,
        agent_id: UUID,
        conversation_id: UUID,
        allow_unassigned: bool = False,
    ) -> Conversation:
        conversation = await self.conversations.get_by_id(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)

        assigned_agent_id = conversation.assigned_agent_id
        if assigned_agent_id is not None and assigned_agent_id != agent_id:
            raise AgentConversationAccessDeniedError(conversation_id, agent_id)
        if assigned_agent_id is None and not allow_unassigned:
            raise AgentConversationAccessDeniedError(conversation_id, agent_id)

        return conversation

    @staticmethod
    def _assert_agent_mode(conversation: Conversation) -> None:
        if ConversationLifecycle.is_read_only(conversation.status):
            raise ConversationClosedError(conversation.id)
        if conversation.status != ConversationStatus.AGENT:
            raise AgentConversationModeError(conversation.id, conversation.status)

    async def _emit_message_created(self, message: Message) -> None:
        await self._safe_publish(
            channels=[conversation_channel(message.conversation_id)],
            event=RealtimeEvent.MESSAGE_CREATED,
            payload={
                "conversation_id": str(message.conversation_id),
                "message": self._message_payload(message),
            },
        )

    async def _emit_conversation_updated(self, conversation: Conversation) -> None:
        await self._safe_publish(
            channels=self._conversation_channels(conversation),
            event=RealtimeEvent.CONVERSATION_UPDATED,
            payload={"conversation": self._conversation_payload(conversation)},
        )

    async def _emit_agent_assigned(
        self, conversation: Conversation, assigned_agent: Agent
    ) -> None:
        await self._safe_publish(
            channels=self._conversation_channels(conversation),
            event=RealtimeEvent.AGENT_ASSIGNED,
            payload={
                "conversation": self._conversation_payload(conversation),
                "agent": self._agent_payload(assigned_agent),
            },
        )

    async def _emit_chat_closed(self, conversation: Conversation) -> None:
        await self._safe_publish(
            channels=self._conversation_channels(conversation),
            event=RealtimeEvent.CHAT_CLOSED,
            payload={"conversation": self._conversation_payload(conversation)},
        )

    async def _emit_agent_presence_changed(self, agent: Agent) -> None:
        await self._safe_publish(
            channels=[AGENT_PRESENCE_CHANNEL, agent_queue_channel(agent.id)],
            event=RealtimeEvent.AGENT_PRESENCE_CHANGED,
            payload={"agent": self._agent_payload(agent)},
        )

    async def _safe_publish(
        self,
        channels: list[str],
        event: RealtimeEvent,
        payload: dict[str, Any],
    ) -> None:
        try:
            await self.realtime.publish(channels, event, payload)
        except Exception:
            return None

    @staticmethod
    def _conversation_channels(conversation: Conversation) -> list[str]:
        channels = [conversation_channel(conversation.id)]
        if conversation.assigned_agent_id is not None:
            channels.append(agent_queue_channel(conversation.assigned_agent_id))
        return channels

    @staticmethod
    def _conversation_payload(conversation: Conversation) -> dict[str, Any]:
        return {
            "id": str(conversation.id),
            "customer_session_id": conversation.customer_session_id,
            "status": conversation.status.value,
            "assigned_agent_id": (
                str(conversation.assigned_agent_id)
                if conversation.assigned_agent_id is not None
                else None
            ),
            "requested_agent_at": (
                conversation.requested_agent_at.isoformat()
                if conversation.requested_agent_at is not None
                else None
            ),
            "closed_at": (
                conversation.closed_at.isoformat()
                if conversation.closed_at is not None
                else None
            ),
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
        }

    @staticmethod
    def _message_payload(message: Message) -> dict[str, Any]:
        return {
            "id": str(message.id),
            "conversation_id": str(message.conversation_id),
            "sender_type": message.sender_type.value,
            "sender_agent_id": (
                str(message.sender_agent_id) if message.sender_agent_id is not None else None
            ),
            "kind": message.kind.value,
            "content": message.content,
            "metadata_json": message.metadata_json,
            "created_at": message.created_at.isoformat(),
        }

    @staticmethod
    def _agent_payload(agent: Agent) -> dict[str, Any]:
        return {
            "id": str(agent.id),
            "display_name": agent.display_name,
            "presence": agent.presence.value,
            "max_active_chats": agent.max_active_chats,
            "created_at": agent.created_at.isoformat(),
            "updated_at": agent.updated_at.isoformat(),
        }
