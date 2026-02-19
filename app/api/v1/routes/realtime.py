import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.core.security import decode_agent_access_token
from app.domain.enums import AgentPresence
from app.infra.db.repositories import (
    AgentRepository,
    AgentUserRepository,
    ConversationRepository,
)
from app.infra.realtime.channels import (
    AGENT_PRESENCE_CHANNEL,
    agent_queue_channel,
    conversation_channel,
)

router = APIRouter()
settings = get_settings()


def _parse_uuid(raw: str | None) -> UUID | None:
    if raw is None:
        return None
    try:
        return UUID(raw)
    except ValueError:
        return None


@router.websocket("/ws")
async def realtime_ws(websocket: WebSocket) -> None:
    hub = getattr(websocket.app.state, "realtime_hub", None)
    if hub is None:
        await websocket.close(code=1011, reason="Realtime hub not initialized")
        return

    try:
        session_factory = get_session_factory()
    except RuntimeError:
        await websocket.close(code=1011, reason="Database session is not initialized")
        return

    role = websocket.query_params.get("role", "").strip().lower()
    requested_conversation_id = _parse_uuid(
        websocket.query_params.get("conversation_id")
    )
    requested_agent_id = _parse_uuid(websocket.query_params.get("agent_id"))
    customer_session_id = websocket.query_params.get("customer_session_id", "").strip()
    tracked_agent_id: UUID | None = None

    initial_channels: list[str] = []

    if role == "customer":
        if requested_conversation_id is None or not customer_session_id:
            await websocket.close(
                code=1008,
                reason=(
                    "Customer websocket requires conversation_id and "
                    "customer_session_id query parameters"
                ),
            )
            return

        async with session_factory() as session:
            conversations = ConversationRepository(session)
            conversation = await conversations.get_by_id(requested_conversation_id)
            if (
                conversation is None
                or conversation.customer_session_id != customer_session_id
            ):
                await websocket.close(
                    code=1008,
                    reason="Conversation access denied for this customer session",
                )
                return

        initial_channels.append(conversation_channel(requested_conversation_id))
    elif role == "agent":
        access_token = websocket.query_params.get("access_token", "").strip()
        if not access_token:
            await websocket.close(
                code=1008,
                reason="Agent websocket requires access_token query parameter",
            )
            return

        try:
            claims = decode_agent_access_token(
                access_token,
                settings.agent_auth_secret,
            )
        except ValueError:
            await websocket.close(code=1008, reason="Invalid or expired agent session")
            return

        resolved_agent_id = claims.agent_id
        if requested_agent_id is not None and requested_agent_id != resolved_agent_id:
            await websocket.close(code=1008, reason="Agent identity mismatch")
            return
        requested_agent_id = resolved_agent_id

        async with session_factory() as session:
            agents = AgentRepository(session)
            users = AgentUserRepository(session)
            conversations = ConversationRepository(session)

            agent_user = await users.get_by_id(claims.user_id)
            if (
                agent_user is None
                or not agent_user.is_active
                or agent_user.agent_id != resolved_agent_id
            ):
                await websocket.close(code=1008, reason="Invalid or expired agent session")
                return

            agent = await agents.get_by_id(requested_agent_id)
            if agent is None:
                await websocket.close(code=1008, reason="Agent not found")
                return

            if requested_conversation_id is not None:
                conversation = await conversations.get_by_id(requested_conversation_id)
                if conversation is None:
                    await websocket.close(code=1008, reason="Conversation not found")
                    return
                if (
                    conversation.assigned_agent_id is not None
                    and conversation.assigned_agent_id != requested_agent_id
                ):
                    await websocket.close(
                        code=1008,
                        reason="Conversation is assigned to another agent",
                    )
                    return

        initial_channels.extend(
            [
                agent_queue_channel(requested_agent_id),
                AGENT_PRESENCE_CHANNEL,
            ]
        )
        tracked_agent_id = requested_agent_id
        if requested_conversation_id is not None:
            initial_channels.append(conversation_channel(requested_conversation_id))
    else:
        await websocket.close(
            code=1008,
            reason="Unsupported role. Use role=customer or role=agent",
        )
        return

    await hub.connect(websocket)
    for channel in initial_channels:
        await hub.subscribe(websocket, channel)

    await websocket.send_json(
        {
            "event": "system.connected",
            "payload": {
                "role": role,
                "channels": initial_channels,
            },
            "sent_at": datetime.now(UTC).isoformat(),
        }
    )

    if tracked_agent_id is not None:
        async with session_factory() as session:
            agents = AgentRepository(session)
            agent = await agents.get_by_id(tracked_agent_id)
            if agent is not None and agent.presence != AgentPresence.ONLINE:
                await agents.update_presence(agent, AgentPresence.ONLINE)
                await session.commit()

    try:
        while True:
            raw_message = await websocket.receive_text()
            if raw_message.strip().lower() == "ping":
                await websocket.send_json(
                    {
                        "event": "system.pong",
                        "payload": {},
                        "sent_at": datetime.now(UTC).isoformat(),
                    }
                )
                continue

            try:
                message = json.loads(raw_message)
            except json.JSONDecodeError:
                await websocket.send_json(
                    {
                        "event": "system.error",
                        "payload": {"detail": "Expected JSON payload"},
                        "sent_at": datetime.now(UTC).isoformat(),
                    }
                )
                continue

            action = message.get("action")
            if action == "ping":
                await websocket.send_json(
                    {
                        "event": "system.pong",
                        "payload": {},
                        "sent_at": datetime.now(UTC).isoformat(),
                    }
                )
                continue

            if role != "agent":
                await websocket.send_json(
                    {
                        "event": "system.error",
                        "payload": {"detail": "Unsupported action for current role"},
                        "sent_at": datetime.now(UTC).isoformat(),
                    }
                )
                continue

            if action == "subscribe_conversation":
                parsed_conversation_id = _parse_uuid(message.get("conversation_id"))
                if parsed_conversation_id is None:
                    await websocket.send_json(
                        {
                            "event": "system.error",
                            "payload": {"detail": "Invalid conversation_id"},
                            "sent_at": datetime.now(UTC).isoformat(),
                        }
                    )
                    continue

                async with session_factory() as session:
                    conversations = ConversationRepository(session)
                    conversation = await conversations.get_by_id(parsed_conversation_id)
                    if conversation is None:
                        await websocket.send_json(
                            {
                                "event": "system.error",
                                "payload": {"detail": "Conversation not found"},
                                "sent_at": datetime.now(UTC).isoformat(),
                            }
                        )
                        continue
                    if (
                        conversation.assigned_agent_id is not None
                        and conversation.assigned_agent_id != requested_agent_id
                    ):
                        await websocket.send_json(
                            {
                                "event": "system.error",
                                "payload": {"detail": "Conversation access denied"},
                                "sent_at": datetime.now(UTC).isoformat(),
                            }
                        )
                        continue

                channel = conversation_channel(parsed_conversation_id)
                await hub.subscribe(websocket, channel)
                await websocket.send_json(
                    {
                        "event": "system.subscribed",
                        "payload": {"channel": channel},
                        "sent_at": datetime.now(UTC).isoformat(),
                    }
                )
                continue

            if action == "unsubscribe_conversation":
                parsed_conversation_id = _parse_uuid(message.get("conversation_id"))
                if parsed_conversation_id is None:
                    await websocket.send_json(
                        {
                            "event": "system.error",
                            "payload": {"detail": "Invalid conversation_id"},
                            "sent_at": datetime.now(UTC).isoformat(),
                        }
                    )
                    continue

                channel = conversation_channel(parsed_conversation_id)
                await hub.unsubscribe(websocket, channel)
                await websocket.send_json(
                    {
                        "event": "system.unsubscribed",
                        "payload": {"channel": channel},
                        "sent_at": datetime.now(UTC).isoformat(),
                    }
                )
                continue

            await websocket.send_json(
                {
                    "event": "system.error",
                    "payload": {"detail": "Unsupported action"},
                    "sent_at": datetime.now(UTC).isoformat(),
                }
            )
    except WebSocketDisconnect:
        return
    finally:
        await hub.disconnect(websocket)
        if tracked_agent_id is None:
            return

        agent_channel = agent_queue_channel(tracked_agent_id)
        if hasattr(hub, "subscriber_count"):
            remaining_connections = int(hub.subscriber_count(agent_channel))
            if remaining_connections > 0:
                return

        async with session_factory() as session:
            agents = AgentRepository(session)
            agent = await agents.get_by_id(tracked_agent_id)
            if agent is None:
                return
            if agent.presence != AgentPresence.OFFLINE:
                await agents.update_presence(agent, AgentPresence.OFFLINE)
                await session.commit()
