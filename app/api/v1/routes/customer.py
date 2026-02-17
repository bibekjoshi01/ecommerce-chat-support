from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.schemas.conversation import (
    EscalateConversationResponse,
    StartConversationRequest,
)
from app.schemas.message import SendMessageRequest

router = APIRouter()


@router.post("/conversations/start")
async def start_conversation(payload: StartConversationRequest) -> dict[str, str]:
    # Placeholder: implemented with service/repository in the next phase.
    if not payload.customer_session_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="customer_session_id required")
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")


@router.post("/conversations/{conversation_id}/messages")
async def post_customer_message(conversation_id: UUID, payload: SendMessageRequest) -> dict[str, str]:
    if not payload.content.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="message content required")
    _ = conversation_id
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")


@router.post("/conversations/{conversation_id}/escalate", response_model=EscalateConversationResponse)
async def escalate_to_agent(conversation_id: UUID) -> EscalateConversationResponse:
    _ = conversation_id
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={"detail": "Not implemented yet", "timestamp": datetime.now(timezone.utc).isoformat()},
    )
