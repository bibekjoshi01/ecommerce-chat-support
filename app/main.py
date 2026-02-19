from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.db import close_engine, init_engine
from app.infra.realtime import InMemoryRealtimeHub

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize infrastructure
    engine = init_engine()
    app.state.db_engine = engine
    app.state.realtime_hub = InMemoryRealtimeHub()

    yield

    # Graceful shutdown
    await close_engine(engine)


app = FastAPI(
    title="E-commerce Support Chat API",
    version="0.1.0",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url="/redoc" if settings.app_env != "production" else None,
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api")


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {"service": "ecommerce-chat-backend", "status": "ok"}
