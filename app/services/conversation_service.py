from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import (
    ConversationStatus,
    MessageKind,
    MessageSenderType,
    TransitionAction,
)
from app.domain.state_machine import ConversationLifecycle
from app.infra.db.models import Agent, Conversation, FaqEntry, Message
from app.infra.db.repositories import (
    AgentRepository,
    ConversationRepository,
    FaqRepository,
    MessageRepository,
)
from app.infra.realtime.channels import agent_queue_channel, conversation_channel
from app.infra.realtime.events import RealtimeEvent
from app.infra.realtime.publisher import NoopRealtimePublisher, RealtimePublisher
from app.services.errors import (
    ConversationAccessDeniedError,
    ConversationClosedError,
    ConversationModeError,
    ConversationNotFoundError,
    FaqNotFoundError,
)


@dataclass(slots=True)
class ConversationBootstrap:
    conversation: Conversation
    quick_questions: list[FaqEntry]
    messages: list[Message]
    show_talk_to_agent: bool


@dataclass(slots=True)
class ConversationMessages:
    conversation: Conversation
    messages: list[Message]


@dataclass(slots=True)
class BotExchange:
    conversation: Conversation
    customer_message: Message
    bot_message: Message
    quick_questions: list[FaqEntry]
    show_talk_to_agent: bool


class ConversationService:
    def __init__(
        self,
        session: AsyncSession,
        conversations: ConversationRepository | None = None,
        messages: MessageRepository | None = None,
        faqs: FaqRepository | None = None,
        agents: AgentRepository | None = None,
        realtime: RealtimePublisher | None = None,
    ) -> None:
        self.session = session
        self.conversations = conversations or ConversationRepository(session)
        self.messages = messages or MessageRepository(session)
        self.faqs = faqs or FaqRepository(session)
        self.agents = agents or AgentRepository(session)
        self.realtime = realtime or NoopRealtimePublisher()

    async def start_customer_conversation(
        self,
        customer_session_id: str | None,
        force_new: bool = False,
    ) -> ConversationBootstrap:
        session_id = self._resolve_customer_session_id(customer_session_id)

        conversation: Conversation | None = None
        if not force_new:
            conversation = await self.conversations.get_latest_active_by_session(
                session_id
            )

        if conversation is None:
            conversation = await self.conversations.create(session_id)
            await self.messages.create(
                conversation_id=conversation.id,
                sender_type=MessageSenderType.BOT,
                kind=MessageKind.EVENT,
                content=(
                    "Hi! I am your support assistant. "
                    "Select a quick question or choose talk to agent."
                ),
                metadata_json={"show_talk_to_agent": True},
            )
            await self.conversations.touch(conversation)

        quick_questions = await self.faqs.list_active()
        conversation_messages = await self.messages.list_by_conversation(
            conversation.id
        )

        await self.session.commit()
        await self.session.refresh(conversation)

        return ConversationBootstrap(
            conversation=conversation,
            quick_questions=quick_questions,
            messages=conversation_messages,
            show_talk_to_agent=ConversationLifecycle.should_show_talk_to_agent(
                conversation.status
            ),
        )

    async def list_quick_questions(self) -> list[FaqEntry]:
        return await self.faqs.list_active()

    async def get_conversation(
        self,
        conversation_id: UUID,
        customer_session_id: str,
    ) -> Conversation:
        return await self._get_conversation_or_raise(
            conversation_id, customer_session_id
        )

    async def get_conversation_messages(
        self,
        conversation_id: UUID,
        customer_session_id: str,
    ) -> ConversationMessages:
        conversation = await self._get_conversation_or_raise(
            conversation_id,
            customer_session_id,
        )
        conversation_messages = await self.messages.list_by_conversation(
            conversation_id
        )
        return ConversationMessages(
            conversation=conversation, messages=conversation_messages
        )

    async def send_quick_reply(
        self,
        conversation_id: UUID,
        faq_slug: str,
        customer_session_id: str,
    ) -> BotExchange:
        conversation = await self._get_conversation_or_raise(
            conversation_id,
            customer_session_id,
        )
        self._assert_bot_mode(conversation)

        faq_entry = await self.faqs.get_active_by_slug(faq_slug)
        if faq_entry is None:
            raise FaqNotFoundError(faq_slug)

        customer_message = await self.messages.create(
            conversation_id=conversation.id,
            sender_type=MessageSenderType.CUSTOMER,
            kind=MessageKind.QUICK_REPLY,
            content=faq_entry.question,
            metadata_json={"faq_slug": faq_entry.slug},
        )

        bot_message = await self.messages.create(
            conversation_id=conversation.id,
            sender_type=MessageSenderType.BOT,
            kind=MessageKind.TEXT,
            content=faq_entry.answer,
            metadata_json={"faq_slug": faq_entry.slug, "show_talk_to_agent": True},
        )

        await self.conversations.touch(conversation)
        quick_questions = await self.faqs.list_active()

        await self.session.commit()
        await self.session.refresh(conversation)

        await self._emit_message_created(customer_message)
        await self._emit_message_created(bot_message)
        await self._emit_conversation_updated(conversation)

        return BotExchange(
            conversation=conversation,
            customer_message=customer_message,
            bot_message=bot_message,
            quick_questions=quick_questions,
            show_talk_to_agent=ConversationLifecycle.should_show_talk_to_agent(
                conversation.status
            ),
        )

    async def send_customer_text_message(
        self,
        conversation_id: UUID,
        content: str,
        customer_session_id: str,
    ) -> BotExchange:
        conversation = await self._get_conversation_or_raise(
            conversation_id,
            customer_session_id,
        )
        self._assert_not_closed(conversation)

        cleaned_content = content.strip()
        customer_message = await self.messages.create(
            conversation_id=conversation.id,
            sender_type=MessageSenderType.CUSTOMER,
            kind=MessageKind.TEXT,
            content=cleaned_content,
        )

        if conversation.status == ConversationStatus.AGENT:
            assigned_agent = await self._resolve_assigned_agent(conversation)
            delivery_event = await self.messages.create(
                conversation_id=conversation.id,
                sender_type=MessageSenderType.SYSTEM,
                kind=MessageKind.EVENT,
                content=(
                    f"Message sent to {assigned_agent.display_name}. "
                    "They will reply shortly."
                ),
                metadata_json={
                    "assigned_agent_id": str(assigned_agent.id),
                    "show_talk_to_agent": False,
                },
            )

            await self.conversations.touch(conversation)
            await self.session.commit()
            await self.session.refresh(conversation)

            await self._emit_message_created(customer_message)
            await self._emit_message_created(delivery_event)
            await self._emit_conversation_updated(conversation)

            return BotExchange(
                conversation=conversation,
                customer_message=customer_message,
                bot_message=delivery_event,
                quick_questions=[],
                show_talk_to_agent=False,
            )

        faq_match = await self.faqs.find_by_question_or_slug(cleaned_content)
        quick_questions = await self.faqs.list_active()

        if faq_match:
            bot_content = faq_match.answer
            bot_metadata: dict | None = {
                "faq_slug": faq_match.slug,
                "show_talk_to_agent": True,
            }
        else:
            prompt_list = ", ".join(
                [question.question for question in quick_questions[:3]]
            )
            if prompt_list:
                bot_content = (
                    "I can help with common questions. "
                    f"Try one of these: {prompt_list}."
                )
            else:
                bot_content = "I can help with common support questions."
            bot_metadata = {"show_talk_to_agent": True}

        bot_message = await self.messages.create(
            conversation_id=conversation.id,
            sender_type=MessageSenderType.BOT,
            kind=MessageKind.TEXT,
            content=bot_content,
            metadata_json=bot_metadata,
        )

        await self.conversations.touch(conversation)
        await self.session.commit()
        await self.session.refresh(conversation)

        await self._emit_message_created(customer_message)
        await self._emit_message_created(bot_message)
        await self._emit_conversation_updated(conversation)

        return BotExchange(
            conversation=conversation,
            customer_message=customer_message,
            bot_message=bot_message,
            quick_questions=quick_questions,
            show_talk_to_agent=ConversationLifecycle.should_show_talk_to_agent(
                conversation.status
            ),
        )

    async def escalate_to_agent(
        self,
        conversation_id: UUID,
        customer_session_id: str,
    ) -> BotExchange:
        conversation = await self._get_conversation_or_raise(
            conversation_id,
            customer_session_id,
        )
        self._assert_not_closed(conversation)

        customer_message = await self.messages.create(
            conversation_id=conversation.id,
            sender_type=MessageSenderType.CUSTOMER,
            kind=MessageKind.QUICK_REPLY,
            content="Talk to an agent",
            metadata_json={"action": "talk_to_agent"},
        )

        assigned_agent = await self._resolve_assigned_agent(conversation)

        if conversation.status != ConversationStatus.AGENT:
            conversation.status = ConversationLifecycle.transition(
                conversation.status, TransitionAction.ESCALATE_TO_AGENT
            )
            conversation.assigned_agent_id = assigned_agent.id
            conversation.requested_agent_at = datetime.now(UTC)
            await self.conversations.touch(conversation)

        system_message = await self.messages.create(
            conversation_id=conversation.id,
            sender_type=MessageSenderType.SYSTEM,
            kind=MessageKind.EVENT,
            content=(
                f"{assigned_agent.display_name} is connected. "
                "You can continue typing your message."
            ),
            metadata_json={
                "assigned_agent_id": str(assigned_agent.id),
                "assigned_agent_name": assigned_agent.display_name,
                "show_talk_to_agent": False,
            },
        )

        await self.session.commit()
        await self.session.refresh(conversation)

        await self._emit_message_created(customer_message)
        await self._emit_message_created(system_message)
        await self._emit_conversation_updated(conversation)
        await self._emit_agent_assigned(conversation, assigned_agent)

        return BotExchange(
            conversation=conversation,
            customer_message=customer_message,
            bot_message=system_message,
            quick_questions=[],
            show_talk_to_agent=False,
        )

    async def _get_conversation_or_raise(
        self,
        conversation_id: UUID,
        customer_session_id: str,
    ) -> Conversation:
        conversation = await self.conversations.get_by_id(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        if conversation.customer_session_id != customer_session_id:
            raise ConversationAccessDeniedError(conversation_id)
        return conversation

    def _resolve_customer_session_id(self, customer_session_id: str | None) -> str:
        if customer_session_id and customer_session_id.strip():
            return customer_session_id.strip()
        return uuid4().hex

    def _assert_not_closed(self, conversation: Conversation) -> None:
        if ConversationLifecycle.is_read_only(conversation.status):
            raise ConversationClosedError(conversation.id)

    def _assert_bot_mode(self, conversation: Conversation) -> None:
        self._assert_not_closed(conversation)
        if conversation.status != ConversationStatus.AUTOMATED:
            raise ConversationModeError(conversation.id, conversation.status)

    async def _resolve_assigned_agent(self, conversation: Conversation) -> Agent:
        if conversation.assigned_agent_id:
            existing = await self.agents.get_by_id(conversation.assigned_agent_id)
            if existing is not None:
                return existing

        return await self._pick_available_agent()

    async def _pick_available_agent(self) -> Agent:
        online_agents = await self.agents.list_online()
        if not online_agents:
            return await self.agents.create(
                display_name="Support Agent",
                max_active_chats=5,
            )

        for agent in online_agents:
            active_count = await self.conversations.count_active_assigned_to_agent(
                agent.id
            )
            if active_count < agent.max_active_chats:
                return agent

        return online_agents[0]

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
