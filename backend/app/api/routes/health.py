from fastapi import APIRouter

from app.domains.system.application.get_health import get_health
from app.domains.system.schemas import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return get_health()
