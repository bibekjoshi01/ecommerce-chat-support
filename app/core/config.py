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


@lru_cache
def get_settings() -> Settings:
    return Settings()
