from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    api_port: int = 8000

    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_db: str = "ecommerce_chat"
    postgres_user: str = "chat_user"
    postgres_password: str = "chat_password"
    database_url_override: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_URL_OVERRIDE", "DATABASE_URL"),
    )
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_auto_create: bool = False
    db_seed_faq_defaults: bool = True

    redis_url: str = "redis://localhost:6379/0"
    agent_auth_secret: str = "local-dev-agent-auth-secret-change-me"
    agent_auth_token_ttl_minutes: int = 480
    cors_allowed_origins_raw: str = "http://127.0.0.1:5173,http://localhost:5173"
    trusted_hosts_raw: str = "127.0.0.1,localhost"
    force_https: bool = False

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allowed_origins_raw.split(",")
            if origin.strip()
        ]

    @property
    def trusted_hosts(self) -> list[str]:
        return [
            host.strip() for host in self.trusted_hosts_raw.split(",") if host.strip()
        ]

    def validate_security_settings(self) -> None:
        if self.app_env.lower() != "production":
            return

        if self.agent_auth_secret == "local-dev-agent-auth-secret-change-me":
            raise ValueError(
                "AGENT_AUTH_SECRET must be overridden in production."
            )
        if len(self.agent_auth_secret) < 32:
            raise ValueError(
                "AGENT_AUTH_SECRET must be at least 32 characters in production."
            )
        if not self.cors_allowed_origins:
            raise ValueError(
                "CORS_ALLOWED_ORIGINS_RAW must define explicit origins in production."
            )
        if "*" in self.cors_allowed_origins:
            raise ValueError("Wildcard CORS origin is not allowed in production.")
        if not self.trusted_hosts:
            raise ValueError(
                "TRUSTED_HOSTS_RAW must define explicit hosts in production."
            )
        if "*" in self.trusted_hosts:
            raise ValueError("Wildcard trusted host is not allowed in production.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
