from fastapi import APIRouter

from app.api.routes.admin import router as admin_router
from app.api.routes.auth import router as auth_router
from app.api.routes.challenges import router as challenges_router
from app.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(health_router)
api_router.include_router(challenges_router, prefix="/challenges")
api_router.include_router(admin_router)
