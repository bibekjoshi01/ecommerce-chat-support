from collections.abc import AsyncIterator

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.infra.db.models import Base
from app.infra.db.seed import seed_default_faq_entries

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
SessionFactory = async_sessionmaker(engine, autoflush=False, expire_on_commit=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session


async def initialize_database() -> None:
    if settings.db_auto_create:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    if settings.db_seed_faq_defaults and await _table_exists("faq_entries"):
        async with SessionFactory() as session:
            await seed_default_faq_entries(session)
            await session.commit()


async def _table_exists(table_name: str) -> bool:
    async with engine.begin() as connection:
        return await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).has_table(table_name)
        )
