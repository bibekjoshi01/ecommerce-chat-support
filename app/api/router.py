from fastapi import APIRouter

from app.api.v1.routes import agent, customer, health, realtime

api_router = APIRouter()
api_router.include_router(health.router, prefix="/v1", tags=["health"])
api_router.include_router(customer.router, prefix="/v1/customer", tags=["customer"])
api_router.include_router(agent.router, prefix="/v1/agent", tags=["agent"])
api_router.include_router(realtime.router, prefix="/v1/realtime", tags=["realtime"])
