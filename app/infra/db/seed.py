from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.domain.enums import AgentPresence
from app.infra.db.models import Agent, AgentUser, FaqEntry

DEFAULT_FAQ_ENTRIES: list[dict[str, str | int | bool]] = [
    {
        "slug": "delivery-date",
        "question": "What is the delivery date?",
        "answer": "Most orders are delivered in 3-5 business days based on your shipping location.",
        "display_order": 1,
        "is_active": True,
    },
    {
        "slug": "return-policy",
        "question": "What is the return policy?",
        "answer": "You can return unused items within 30 days of delivery for a full refund.",
        "display_order": 2,
        "is_active": True,
    },
    {
        "slug": "order-status",
        "question": "Where is my order?",
        "answer": "Share your order ID and I can help check the latest order tracking status.",
        "display_order": 3,
        "is_active": True,
    },
]

DEFAULT_AGENT_ACCOUNTS: list[dict[str, str | int]] = [
    {
        "display_name": "Bibek Joshi",
        "username": "bibek.joshi",
        "password": "BibekJoshi@123!",
        "max_active_chats": 5,
    },
    {
        "display_name": "John Doe",
        "username": "john.doe",
        "password": "AgentPass123!",
        "max_active_chats": 5,
    },
    {
        "display_name": "Admin",
        "username": "admin",
        "password": "Admin@123",
        "max_active_chats": 5,
    },
]


async def seed_default_faq_entries(session: AsyncSession) -> None:
    existing_rows = await session.execute(select(FaqEntry.slug))
    existing_slugs = {slug for slug in existing_rows.scalars().all()}

    inserts: list[FaqEntry] = []
    for item in DEFAULT_FAQ_ENTRIES:
        slug = str(item["slug"])
        if slug in existing_slugs:
            continue

        inserts.append(
            FaqEntry(
                slug=slug,
                question=str(item["question"]),
                answer=str(item["answer"]),
                display_order=int(item["display_order"]),
                is_active=bool(item["is_active"]),
            )
        )

    if inserts:
        session.add_all(inserts)
        await session.flush()


async def seed_default_agent_accounts(session: AsyncSession) -> None:
    existing_user_rows = await session.execute(select(AgentUser.username))
    existing_usernames = {
        username.strip().lower() for username in existing_user_rows.scalars().all()
    }

    for item in DEFAULT_AGENT_ACCOUNTS:
        username = str(item["username"]).strip().lower()
        if username in existing_usernames:
            continue

        display_name = str(item["display_name"]).strip()
        password = str(item["password"])
        max_active_chats = int(item["max_active_chats"])

        agent = Agent(
            display_name=display_name,
            max_active_chats=max_active_chats,
            presence=AgentPresence.OFFLINE,
        )
        session.add(agent)
        await session.flush()

        session.add(
            AgentUser(
                agent_id=agent.id,
                username=username,
                password_hash=hash_password(password),
                is_active=True,
            )
        )
        await session.flush()
