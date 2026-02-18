from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
async def db_health(session: AsyncSession = Depends(get_db_session)):
    await session.execute(text("SELECT 1"))
    return {"db": "ok"}
