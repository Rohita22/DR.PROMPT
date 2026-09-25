from app.domains.system.schemas import HealthResponse


def get_health() -> HealthResponse:
    return HealthResponse()
