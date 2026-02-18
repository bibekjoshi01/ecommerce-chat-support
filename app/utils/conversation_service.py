from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.errors import (
    ConversationAccessDeniedError,
    ConversationClosedError,
    ConversationModeError,
    ConversationNotFoundError,
    FaqNotFoundError,
)
from app.domain.enums import ConversationStatus, MessageKind, MessageSenderType
from app.domain.state_machine import ConversationLifecycle
from app.infra.db.models import Conversation, FaqEntry, Message
from app.infra.db.repositories import ConversationRepository, FaqRepository, MessageRepository


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
    ) -> None:
        self.session = session
        self.conversations = conversations or ConversationRepository(session)
        self.messages = messages or MessageRepository(session)
        self.faqs = faqs or FaqRepository(session)

    async def start_customer_conversation(
        self,
        customer_session_id: str | None,
        force_new: bool = False,
    ) -> ConversationBootstrap:
        session_id = self._resolve_customer_session_id(customer_session_id)

        conversation: Conversation | None = None
        if not force_new:
            conversation = await self.conversations.get_latest_active_by_session(session_id)

        if conversation is None:
            conversation = await self.conversations.create(session_id)
            await self.messages.create(
                conversation_id=conversation.id,
                sender_type=MessageSenderType.BOT,
                kind=MessageKind.EVENT,
                content="Hi! I am your support assistant. Select a quick question or type your message.",
                metadata_json={"show_talk_to_agent": True},
            )
            await self.conversations.touch(conversation)

        quick_questions = await self.faqs.list_active()
        conversation_messages = await self.messages.list_by_conversation(conversation.id)

        await self.session.commit()
        await self.session.refresh(conversation)

        return ConversationBootstrap(
            conversation=conversation,
            quick_questions=quick_questions,
            messages=conversation_messages,
            show_talk_to_agent=ConversationLifecycle.should_show_talk_to_agent(conversation.status),
        )

    async def list_quick_questions(self) -> list[FaqEntry]:
        return await self.faqs.list_active()

    async def get_conversation(
        self,
        conversation_id: UUID,
        customer_session_id: str,
    ) -> Conversation:
        return await self._get_conversation_or_raise(conversation_id, customer_session_id)

    async def get_conversation_messages(
        self,
        conversation_id: UUID,
        customer_session_id: str,
    ) -> ConversationMessages:
        conversation = await self._get_conversation_or_raise(
            conversation_id,
            customer_session_id,
        )
        conversation_messages = await self.messages.list_by_conversation(conversation_id)
        return ConversationMessages(conversation=conversation, messages=conversation_messages)

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

        return BotExchange(
            conversation=conversation,
            customer_message=customer_message,
            bot_message=bot_message,
            quick_questions=quick_questions,
            show_talk_to_agent=ConversationLifecycle.should_show_talk_to_agent(conversation.status),
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
        self._assert_bot_mode(conversation)

        cleaned_content = content.strip()
        customer_message = await self.messages.create(
            conversation_id=conversation.id,
            sender_type=MessageSenderType.CUSTOMER,
            kind=MessageKind.TEXT,
            content=cleaned_content,
        )

        faq_match = await self.faqs.find_by_question_or_slug(cleaned_content)
        quick_questions = await self.faqs.list_active()

        if faq_match:
            bot_content = faq_match.answer
            bot_metadata: dict | None = {"faq_slug": faq_match.slug, "show_talk_to_agent": True}
        else:
            prompt_list = ", ".join([question.question for question in quick_questions[:3]])
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

        return BotExchange(
            conversation=conversation,
            customer_message=customer_message,
            bot_message=bot_message,
            quick_questions=quick_questions,
            show_talk_to_agent=ConversationLifecycle.should_show_talk_to_agent(conversation.status),
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

    def _assert_bot_mode(self, conversation: Conversation) -> None:
        if ConversationLifecycle.is_read_only(conversation.status):
            raise ConversationClosedError(conversation.id)
        if conversation.status != ConversationStatus.AUTOMATED:
            raise ConversationModeError(conversation.id, conversation.status)
