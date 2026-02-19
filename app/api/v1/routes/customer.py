from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.conversation_service import (
    BotExchange,
    ConversationBootstrap,
    ConversationMessages,
    ConversationService,
)
from app.services.errors import (
    ConversationAccessDeniedError,
    ConversationClosedError,
    ConversationModeError,
    ConversationNotFoundError,
    FaqNotFoundError,
)
from app.core.db import get_db_session
from app.schemas.customer_chat import (
    BotExchangeResponse,
    ConversationBootstrapResponse,
    ConversationMessagesResponse,
    ConversationResponse,
    CustomerTextMessageRequest,
    QuickQuestionResponse,
    StartConversationRequest,
)
from app.schemas.message import MessageResponse

router = APIRouter()


async def get_conversation_service(
    session: AsyncSession = Depends(get_db_session),
) -> ConversationService:
    return ConversationService(session)


async def get_customer_session_id(
    x_customer_session_id: str = Header(
        alias="X-Customer-Session-Id",
        min_length=8,
        max_length=120,
    ),
) -> str:
    return x_customer_session_id.strip()


def _to_message_response(message) -> MessageResponse:
    return MessageResponse.model_validate(message)


def _to_conversation_response(conversation) -> ConversationResponse:
    return ConversationResponse.model_validate(conversation)


def _to_quick_questions(entries) -> list[QuickQuestionResponse]:
    return [
        QuickQuestionResponse(slug=entry.slug, question=entry.question)
        for entry in entries
    ]


def _to_bootstrap_response(
    result: ConversationBootstrap,
) -> ConversationBootstrapResponse:
    return ConversationBootstrapResponse(
        conversation=_to_conversation_response(result.conversation),
        quick_questions=_to_quick_questions(result.quick_questions),
        messages=[_to_message_response(message) for message in result.messages],
        show_talk_to_agent=result.show_talk_to_agent,
    )


def _to_messages_response(result: ConversationMessages) -> ConversationMessagesResponse:
    return ConversationMessagesResponse(
        conversation=_to_conversation_response(result.conversation),
        messages=[_to_message_response(message) for message in result.messages],
    )


def _to_exchange_response(result: BotExchange) -> BotExchangeResponse:
    return BotExchangeResponse(
        conversation=_to_conversation_response(result.conversation),
        customer_message=_to_message_response(result.customer_message),
        bot_message=_to_message_response(result.bot_message),
        quick_questions=_to_quick_questions(result.quick_questions),
        show_talk_to_agent=result.show_talk_to_agent,
    )


def _raise_for_service_error(exc: Exception) -> None:
    if isinstance(exc, ConversationAccessDeniedError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    if isinstance(exc, ConversationNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    if isinstance(exc, FaqNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    if isinstance(exc, (ConversationClosedError, ConversationModeError)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    raise exc


@router.get("/quick-questions", response_model=list[QuickQuestionResponse])
async def list_quick_questions(
    service: ConversationService = Depends(get_conversation_service),
) -> list[QuickQuestionResponse]:
    entries = await service.list_quick_questions()
    return _to_quick_questions(entries)


@router.post("/conversations/start", response_model=ConversationBootstrapResponse)
async def start_conversation(
    payload: StartConversationRequest,
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationBootstrapResponse:
    result = await service.start_customer_conversation(
        customer_session_id=payload.customer_session_id,
        force_new=payload.force_new,
    )
    return _to_bootstrap_response(result)


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    service: ConversationService = Depends(get_conversation_service),
    customer_session_id: str = Depends(get_customer_session_id),
) -> ConversationResponse:
    try:
        conversation = await service.get_conversation(
            conversation_id,
            customer_session_id,
        )
    except (
        ConversationAccessDeniedError,
        ConversationNotFoundError,
        FaqNotFoundError,
        ConversationClosedError,
        ConversationModeError,
    ) as exc:
        _raise_for_service_error(exc)
    return _to_conversation_response(conversation)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=ConversationMessagesResponse,
)
async def get_conversation_messages(
    conversation_id: UUID,
    service: ConversationService = Depends(get_conversation_service),
    customer_session_id: str = Depends(get_customer_session_id),
) -> ConversationMessagesResponse:
    try:
        result = await service.get_conversation_messages(
            conversation_id,
            customer_session_id,
        )
    except (
        ConversationAccessDeniedError,
        ConversationNotFoundError,
        FaqNotFoundError,
        ConversationClosedError,
        ConversationModeError,
    ) as exc:
        _raise_for_service_error(exc)
    return _to_messages_response(result)


@router.post(
    "/conversations/{conversation_id}/quick-replies/{faq_slug}",
    response_model=BotExchangeResponse,
)
async def send_quick_reply(
    conversation_id: UUID,
    faq_slug: str,
    service: ConversationService = Depends(get_conversation_service),
    customer_session_id: str = Depends(get_customer_session_id),
) -> BotExchangeResponse:
    try:
        result = await service.send_quick_reply(
            conversation_id=conversation_id,
            faq_slug=faq_slug,
            customer_session_id=customer_session_id,
        )
    except (
        ConversationAccessDeniedError,
        ConversationNotFoundError,
        FaqNotFoundError,
        ConversationClosedError,
        ConversationModeError,
    ) as exc:
        _raise_for_service_error(exc)
    return _to_exchange_response(result)


@router.post(
    "/conversations/{conversation_id}/messages", response_model=BotExchangeResponse
)
async def post_customer_message(
    conversation_id: UUID,
    payload: CustomerTextMessageRequest,
    service: ConversationService = Depends(get_conversation_service),
    customer_session_id: str = Depends(get_customer_session_id),
) -> BotExchangeResponse:
    try:
        result = await service.send_customer_text_message(
            conversation_id=conversation_id,
            content=payload.content,
            customer_session_id=customer_session_id,
        )
    except (
        ConversationAccessDeniedError,
        ConversationNotFoundError,
        FaqNotFoundError,
        ConversationClosedError,
        ConversationModeError,
    ) as exc:
        _raise_for_service_error(exc)
    return _to_exchange_response(result)


@router.post(
    "/conversations/{conversation_id}/escalate",
    response_model=BotExchangeResponse,
)
async def escalate_to_agent(
    conversation_id: UUID,
    service: ConversationService = Depends(get_conversation_service),
    customer_session_id: str = Depends(get_customer_session_id),
) -> BotExchangeResponse:
    try:
        result = await service.escalate_to_agent(
            conversation_id=conversation_id,
            customer_session_id=customer_session_id,
        )
    except (
        ConversationAccessDeniedError,
        ConversationNotFoundError,
        FaqNotFoundError,
        ConversationClosedError,
        ConversationModeError,
    ) as exc:
        _raise_for_service_error(exc)
    return _to_exchange_response(result)
