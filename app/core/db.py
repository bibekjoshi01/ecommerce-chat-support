from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)

from app.core.config import get_settings

settings = get_settings()

_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine() -> AsyncEngine:
    global _session_factory

    engine = create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_pre_ping=True,
        echo=False,
    )

    _session_factory = async_sessionmaker(
        engine,
        autoflush=False,
        expire_on_commit=False,
    )

    return engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Database not initialized")

    return _session_factory


async def close_engine(engine: AsyncEngine) -> None:
    await engine.dispose()


async def get_db_session() -> AsyncIterator[AsyncSession]:
    session_factory = get_session_factory()

    async with session_factory() as session:
        yield session
