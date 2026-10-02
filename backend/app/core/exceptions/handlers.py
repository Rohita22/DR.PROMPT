from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.application.admin.errors import (
    AdminChallengeConflictError,
    AdminChallengeNotFoundError,
    AdminChallengeStateError,
)
from app.application.challenges.errors import PromptTooLongError
from app.core.exceptions.errors import (
    ApplicationExecutionInProgressError,
    ApplicationIdempotencyKeyError,
    ApplicationRateLimitError,
    AuthenticationError,
    AuthenticationServiceError,
    AuthorizationError,
    DomainError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    PersistenceError,
)
from app.domains.application.errors import (
    ApplicationConfigurationError,
    ApplicationEnvironmentError,
    WorkspacePathError,
)
from app.domains.challenges.errors import ChallengeNotFoundError
from app.domains.evaluation.errors import HiddenEvaluationUnavailableError
from app.domains.execution.errors import UnsupportedChallengeTypeError


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


def register_exception_handlers(app: FastAPI) -> None:
    def response_for(
        exc: DomainError,
        status_code: int,
        *,
        headers: dict[str, str] | None = None,
    ) -> JSONResponse:
        payload = ErrorResponse(error=ErrorDetail(code=exc.code, message=exc.message))
        return JSONResponse(
            status_code=status_code,
            content=payload.model_dump(),
            headers=headers,
        )

    @app.exception_handler(AuthenticationError)
    async def handle_authentication_error(
        _request: Request,
        exc: AuthenticationError,
    ) -> JSONResponse:
        return response_for(
            exc,
            status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(ApplicationRateLimitError)
    async def handle_application_rate_limit(
        _request: Request,
        exc: ApplicationRateLimitError,
    ) -> JSONResponse:
        return response_for(
            exc,
            status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )

    @app.exception_handler(ApplicationExecutionInProgressError)
    async def handle_application_execution_in_progress(
        _request: Request,
        exc: ApplicationExecutionInProgressError,
    ) -> JSONResponse:
        return response_for(exc, status.HTTP_409_CONFLICT)

    @app.exception_handler(ApplicationIdempotencyKeyError)
    async def handle_application_idempotency_key(
        _request: Request,
        exc: ApplicationIdempotencyKeyError,
    ) -> JSONResponse:
        return response_for(exc, status.HTTP_422_UNPROCESSABLE_CONTENT)

    @app.exception_handler(AuthorizationError)
    async def handle_authorization_error(
        _request: Request,
        exc: AuthorizationError,
    ) -> JSONResponse:
        return response_for(exc, status.HTTP_403_FORBIDDEN)

    @app.exception_handler(AuthenticationServiceError)
    async def handle_authentication_service_error(
        _request: Request,
        exc: AuthenticationServiceError,
    ) -> JSONResponse:
        return response_for(exc, status.HTTP_503_SERVICE_UNAVAILABLE)

    @app.exception_handler(ChallengeNotFoundError)
    async def handle_challenge_not_found(
        _request: Request,
        exc: ChallengeNotFoundError,
    ) -> JSONResponse:
        return response_for(exc, status.HTTP_404_NOT_FOUND)

    @app.exception_handler(LLMRateLimitError)
    async def handle_llm_rate_limit(
        _request: Request,
        exc: LLMRateLimitError,
    ) -> JSONResponse:
        return response_for(exc, status.HTTP_429_TOO_MANY_REQUESTS)

    @app.exception_handler(LLMTimeoutError)
    async def handle_llm_timeout(
        _request: Request,
        exc: LLMTimeoutError,
    ) -> JSONResponse:
        return response_for(exc, status.HTTP_504_GATEWAY_TIMEOUT)

    @app.exception_handler(LLMProviderError)
    async def handle_llm_provider_error(
        _request: Request,
        exc: LLMProviderError,
    ) -> JSONResponse:
        return response_for(exc, status.HTTP_502_BAD_GATEWAY)

    @app.exception_handler(HiddenEvaluationUnavailableError)
    async def handle_hidden_evaluation_unavailable(
        _request: Request,
        exc: HiddenEvaluationUnavailableError,
    ) -> JSONResponse:
        return response_for(exc, status.HTTP_503_SERVICE_UNAVAILABLE)

    @app.exception_handler(UnsupportedChallengeTypeError)
    async def handle_unsupported_challenge_type(
        _request: Request,
        exc: UnsupportedChallengeTypeError,
    ) -> JSONResponse:
        return response_for(exc, status.HTTP_503_SERVICE_UNAVAILABLE)

    @app.exception_handler(ApplicationEnvironmentError)
    @app.exception_handler(ApplicationConfigurationError)
    @app.exception_handler(WorkspacePathError)
    async def handle_application_unavailable(
        _request: Request,
        exc: DomainError,
    ) -> JSONResponse:
        # Infrastructure or trusted-configuration failures: never scored, never detailed.
        return response_for(exc, status.HTTP_503_SERVICE_UNAVAILABLE)

    @app.exception_handler(PromptTooLongError)
    async def handle_prompt_too_long(
        _request: Request,
        exc: PromptTooLongError,
    ) -> JSONResponse:
        return response_for(exc, status.HTTP_422_UNPROCESSABLE_CONTENT)

    @app.exception_handler(PersistenceError)
    async def handle_persistence_error(
        _request: Request,
        exc: PersistenceError,
    ) -> JSONResponse:
        return response_for(exc, status.HTTP_503_SERVICE_UNAVAILABLE)

    @app.exception_handler(AdminChallengeNotFoundError)
    async def handle_admin_challenge_not_found(
        _request: Request,
        exc: AdminChallengeNotFoundError,
    ) -> JSONResponse:
        return response_for(exc, status.HTTP_404_NOT_FOUND)

    @app.exception_handler(AdminChallengeConflictError)
    async def handle_admin_challenge_conflict(
        _request: Request,
        exc: AdminChallengeConflictError,
    ) -> JSONResponse:
        return response_for(exc, status.HTTP_409_CONFLICT)

    @app.exception_handler(AdminChallengeStateError)
    async def handle_admin_challenge_state(
        _request: Request,
        exc: AdminChallengeStateError,
    ) -> JSONResponse:
        return response_for(exc, status.HTTP_409_CONFLICT)

    @app.exception_handler(DomainError)
    async def handle_domain_error(_request: Request, exc: DomainError) -> JSONResponse:
        return response_for(exc, status.HTTP_400_BAD_REQUEST)
