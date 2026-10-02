from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import (
    ApplicationExecutionInProgressError,
    ApplicationIdempotencyKeyError,
    ApplicationRateLimitError,
)
from app.core.exceptions.handlers import register_exception_handlers


def guarded_app() -> FastAPI:
    application = FastAPI()
    register_exception_handlers(application)

    @application.get("/cooldown")
    async def cooldown() -> None:
        raise ApplicationRateLimitError(7, "run")

    @application.get("/active")
    async def active() -> None:
        raise ApplicationExecutionInProgressError()

    @application.get("/key")
    async def key() -> None:
        raise ApplicationIdempotencyKeyError()

    return application


def test_local_cooldown_is_429_with_retry_after() -> None:
    response = TestClient(guarded_app()).get("/cooldown")
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "7"
    assert response.json()["error"]["code"] == "application_rate_limited"


def test_active_execution_and_missing_key_have_distinct_errors() -> None:
    client = TestClient(guarded_app())
    active = client.get("/active")
    missing_key = client.get("/key")
    assert (active.status_code, active.json()["error"]["code"]) == (
        409,
        "application_execution_in_progress",
    )
    assert (missing_key.status_code, missing_key.json()["error"]["code"]) == (
        422,
        "application_idempotency_key_required",
    )
