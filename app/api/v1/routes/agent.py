from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db_session
from app.core.security import decode_agent_access_token
from app.domain.enums import ConversationStatus
from app.infra.db.repositories import AgentUserRepository
from app.schemas.agent_auth import AgentLoginRequest, AgentSessionResponse
from app.schemas.agent_chat import (
    AgentCloseConversationResponse,
    AgentConversationListResponse,
    AgentConversationMessagesResponse,
    AgentConversationResponse,
    AgentMessageExchangeResponse,
    AgentResponse,
    RegisterAgentRequest,
    SetAgentPresenceRequest,
)
from app.schemas.message import MessageResponse, SendMessageRequest
from app.services.agent_auth_service import AgentAuthService
from app.services.agent_service import (
    AgentCloseResult,
    AgentConversationMessages,
    AgentMessageResult,
    AgentService,
)
from app.services.errors import (
    AgentAuthenticationError,
    AgentConversationAccessDeniedError,
    AgentConversationModeError,
    AgentNotFoundError,
    ConversationClosedError,
    ConversationNotFoundError,
)

router = APIRouter()
settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)


async def get_agent_service(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> AgentService:
    realtime = getattr(request.app.state, "realtime_hub", None)
    return AgentService(session=session, realtime=realtime)


async def get_agent_auth_service(
    session: AsyncSession = Depends(get_db_session),
) -> AgentAuthService:
    return AgentAuthService(session=session)


async def get_agent_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> UUID:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization credentials",
        )

    try:
        claims = decode_agent_access_token(
            credentials.credentials,
            settings.agent_auth_secret,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired agent session",
        ) from exc

    users = AgentUserRepository(session)
    agent_user = await users.get_by_id(claims.user_id)
    if (
        agent_user is None
        or not agent_user.is_active
        or agent_user.agent_id != claims.agent_id
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired agent session",
        )

    return agent_user.agent_id


def _to_agent_response(agent) -> AgentResponse:
    return AgentResponse.model_validate(agent)


def _to_conversation_response(conversation) -> AgentConversationResponse:
    return AgentConversationResponse.model_validate(conversation)


def _to_messages_response(
    result: AgentConversationMessages,
) -> AgentConversationMessagesResponse:
    return AgentConversationMessagesResponse(
        conversation=_to_conversation_response(result.conversation),
        messages=[MessageResponse.model_validate(message) for message in result.messages],
    )


def _to_exchange_response(result: AgentMessageResult) -> AgentMessageExchangeResponse:
    return AgentMessageExchangeResponse(
        conversation=_to_conversation_response(result.conversation),
        message=MessageResponse.model_validate(result.message),
    )


def _to_close_response(result: AgentCloseResult) -> AgentCloseConversationResponse:
    return AgentCloseConversationResponse(
        conversation=_to_conversation_response(result.conversation),
        system_message=(
            MessageResponse.model_validate(result.system_message)
            if result.system_message is not None
            else None
        ),
    )


def _raise_for_service_error(exc: Exception) -> None:
    if isinstance(exc, AgentNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, ConversationNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, AgentConversationAccessDeniedError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if isinstance(exc, (ConversationClosedError, AgentConversationModeError)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    raise exc


@router.post("/register", response_model=AgentResponse)
async def register_agent(
    payload: RegisterAgentRequest,
    service: AgentService = Depends(get_agent_service),
) -> AgentResponse:
    agent = await service.register_agent(
        display_name=payload.display_name,
        max_active_chats=payload.max_active_chats,
        start_online=payload.start_online,
    )
    return _to_agent_response(agent)


@router.post("/auth/login", response_model=AgentSessionResponse)
async def login_agent(
    payload: AgentLoginRequest,
    service: AgentAuthService = Depends(get_agent_auth_service),
) -> AgentSessionResponse:
    try:
        result = await service.login(
            username=payload.username,
            password=payload.password,
        )
    except AgentAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    return AgentSessionResponse(
        access_token=result.access_token,
        token_type=result.token_type,
        expires_at=result.expires_at,
        username=result.username,
        agent=_to_agent_response(result.agent),
    )


@router.get("/me", response_model=AgentResponse)
async def get_agent_profile(
    service: AgentService = Depends(get_agent_service),
    agent_id: UUID = Depends(get_agent_id),
) -> AgentResponse:
    try:
        agent = await service.get_agent(agent_id)
    except AgentNotFoundError as exc:
        _raise_for_service_error(exc)
    return _to_agent_response(agent)


@router.post("/presence", response_model=AgentResponse)
async def set_agent_presence(
    payload: SetAgentPresenceRequest,
    service: AgentService = Depends(get_agent_service),
    agent_id: UUID = Depends(get_agent_id),
) -> AgentResponse:
    try:
        agent = await service.set_presence(agent_id=agent_id, presence=payload.presence)
    except (
        AgentNotFoundError,
        ConversationNotFoundError,
        AgentConversationAccessDeniedError,
        ConversationClosedError,
        AgentConversationModeError,
        ValueError,
    ) as exc:
        _raise_for_service_error(exc)
    return _to_agent_response(agent)


@router.get("/conversations", response_model=AgentConversationListResponse)
async def list_agent_conversations(
    status_filter: ConversationStatus | None = Query(default=None, alias="status"),
    service: AgentService = Depends(get_agent_service),
    agent_id: UUID = Depends(get_agent_id),
) -> AgentConversationListResponse:
    try:
        conversations = await service.list_conversations(
            agent_id=agent_id, status_filter=status_filter
        )
    except (
        AgentNotFoundError,
        ConversationNotFoundError,
        AgentConversationAccessDeniedError,
        ConversationClosedError,
        AgentConversationModeError,
        ValueError,
    ) as exc:
        _raise_for_service_error(exc)
    return AgentConversationListResponse(
        items=[_to_conversation_response(conversation) for conversation in conversations]
    )


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=AgentConversationMessagesResponse,
)
async def get_agent_conversation_messages(
    conversation_id: UUID,
    service: AgentService = Depends(get_agent_service),
    agent_id: UUID = Depends(get_agent_id),
) -> AgentConversationMessagesResponse:
    try:
        result = await service.get_conversation_messages(
            agent_id=agent_id,
            conversation_id=conversation_id,
        )
    except (
        AgentNotFoundError,
        ConversationNotFoundError,
        AgentConversationAccessDeniedError,
        ConversationClosedError,
        AgentConversationModeError,
        ValueError,
    ) as exc:
        _raise_for_service_error(exc)
    return _to_messages_response(result)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=AgentMessageExchangeResponse,
)
async def post_agent_message(
    conversation_id: UUID,
    payload: SendMessageRequest,
    service: AgentService = Depends(get_agent_service),
    agent_id: UUID = Depends(get_agent_id),
) -> AgentMessageExchangeResponse:
    try:
        result = await service.send_agent_message(
            agent_id=agent_id,
            conversation_id=conversation_id,
            content=payload.content,
        )
    except (
        AgentNotFoundError,
        ConversationNotFoundError,
        AgentConversationAccessDeniedError,
        ConversationClosedError,
        AgentConversationModeError,
        ValueError,
    ) as exc:
        _raise_for_service_error(exc)
    return _to_exchange_response(result)


@router.post(
    "/conversations/{conversation_id}/close",
    response_model=AgentCloseConversationResponse,
)
async def close_conversation(
    conversation_id: UUID,
    service: AgentService = Depends(get_agent_service),
    agent_id: UUID = Depends(get_agent_id),
) -> AgentCloseConversationResponse:
    try:
        result = await service.close_conversation(
            agent_id=agent_id,
            conversation_id=conversation_id,
        )
    except (
        AgentNotFoundError,
        ConversationNotFoundError,
        AgentConversationAccessDeniedError,
        ConversationClosedError,
        AgentConversationModeError,
        ValueError,
    ) as exc:
        _raise_for_service_error(exc)
    return _to_close_response(result)
