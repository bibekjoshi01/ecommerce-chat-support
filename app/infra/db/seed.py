from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import FaqEntry

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
