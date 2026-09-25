from fastapi import APIRouter

from app.api.routes.challenges import router as challenges_router
from app.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(challenges_router, prefix="/challenges")
