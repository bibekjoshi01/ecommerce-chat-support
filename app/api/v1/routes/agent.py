from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.domain.enums import ConversationStatus
from app.schemas.message import SendMessageRequest

router = APIRouter()


@router.get("/conversations")
async def list_agent_conversations(status_filter: ConversationStatus | None = Query(default=None)) -> dict[str, str]:
    _ = status_filter
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")


@router.post("/conversations/{conversation_id}/messages")
async def post_agent_message(conversation_id: UUID, payload: SendMessageRequest) -> dict[str, str]:
    _ = conversation_id
    _ = payload
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")


@router.post("/conversations/{conversation_id}/close")
async def close_conversation(conversation_id: UUID) -> dict[str, str]:
    _ = conversation_id
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")
