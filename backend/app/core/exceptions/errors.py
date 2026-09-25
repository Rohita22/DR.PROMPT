class DomainError(Exception):
    """Base for expected business-rule failures that may cross into the API layer."""

    code = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EvaluationError(DomainError):
    code = "evaluation_error"


class LLMProviderError(DomainError):
    code = "llm_provider_error"


class LLMAuthenticationError(LLMProviderError):
    code = "llm_authentication_error"


class LLMRateLimitError(LLMProviderError):
    code = "llm_rate_limit_error"

    def __init__(
        self,
        message: str = "The model provider rate limit was reached.",
        *,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class LLMTimeoutError(LLMProviderError):
    code = "llm_timeout_error"


class LLMMalformedResponseError(LLMProviderError):
    code = "llm_malformed_response"
