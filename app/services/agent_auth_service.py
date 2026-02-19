from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_agent_access_token, verify_password
from app.infra.db.models import Agent
from app.infra.db.repositories import AgentRepository, AgentUserRepository
from app.services.errors import AgentAuthenticationError


@dataclass(slots=True)
class AgentLoginResult:
    access_token: str
    token_type: str
    expires_at: datetime
    username: str
    agent: Agent


class AgentAuthService:
    def __init__(
        self,
        session: AsyncSession,
        agents: AgentRepository | None = None,
        users: AgentUserRepository | None = None,
    ) -> None:
        self.session = session
        self.agents = agents or AgentRepository(session)
        self.users = users or AgentUserRepository(session)
        self.settings = get_settings()

    async def login(self, username: str, password: str) -> AgentLoginResult:
        normalized_username = username.strip().lower()
        if not normalized_username:
            raise AgentAuthenticationError()

        agent_user = await self.users.get_by_username(normalized_username)
        if agent_user is None:
            raise AgentAuthenticationError()
        if not agent_user.is_active:
            raise AgentAuthenticationError("Agent account is inactive")
        if not verify_password(password, agent_user.password_hash):
            raise AgentAuthenticationError()

        agent = await self.agents.get_by_id(agent_user.agent_id)
        if agent is None:
            raise AgentAuthenticationError()

        token, expires_at = create_agent_access_token(
            user_id=agent_user.id,
            agent_id=agent.id,
            secret=self.settings.agent_auth_secret,
            ttl_minutes=self.settings.agent_auth_token_ttl_minutes,
        )

        return AgentLoginResult(
            access_token=token,
            token_type="bearer",
            expires_at=expires_at,
            username=agent_user.username,
            agent=agent,
        )
