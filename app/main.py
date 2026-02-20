from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.db import close_engine, get_session_factory, init_engine
from app.domain.enums import AgentPresence
from app.infra.db.repositories import AgentRepository
from app.infra.realtime import InMemoryRealtimeHub

settings = get_settings()
settings.validate_security_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize infrastructure
    engine = init_engine()
    app.state.db_engine = engine
    app.state.realtime_hub = InMemoryRealtimeHub()

    session_factory = get_session_factory()
    async with session_factory() as session:
        agents = AgentRepository(session)
        await agents.set_all_presence(AgentPresence.OFFLINE)
        await session.commit()

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

if settings.trusted_hosts:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.trusted_hosts,
    )

if settings.force_https:
    app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Customer-Session-Id"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault(
        "Referrer-Policy",
        "strict-origin-when-cross-origin",
    )
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=()",
    )
    if settings.force_https:
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
    return response


app.include_router(api_router, prefix="/api")


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {"service": "ecommerce-chat-backend", "status": "ok"}
