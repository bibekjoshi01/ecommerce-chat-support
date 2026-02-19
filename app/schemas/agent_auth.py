from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.agent_chat import AgentResponse


class AgentLoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=6, max_length=128)


class AgentSessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    username: str
    agent: AgentResponse
