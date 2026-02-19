import asyncio

from app.core.db import close_engine, get_session_factory, init_engine
from app.infra.db.seed import seed_default_agent_accounts, seed_default_faq_entries


async def main() -> None:
    engine = init_engine()
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            await seed_default_faq_entries(session)
            await seed_default_agent_accounts(session)
            await session.commit()
    finally:
        print("Successfully loaded data !")
        await close_engine(engine)


if __name__ == "__main__":
    asyncio.run(main())
