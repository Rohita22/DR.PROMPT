from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.exceptions.errors import (
    DomainError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.domains.challenges.errors import ChallengeNotFoundError


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


def register_exception_handlers(app: FastAPI) -> None:
    def response_for(exc: DomainError, status_code: int) -> JSONResponse:
        payload = ErrorResponse(error=ErrorDetail(code=exc.code, message=exc.message))
        return JSONResponse(status_code=status_code, content=payload.model_dump())

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

    @app.exception_handler(DomainError)
    async def handle_domain_error(_request: Request, exc: DomainError) -> JSONResponse:
        return response_for(exc, status.HTTP_400_BAD_REQUEST)
