import json
from collections.abc import Iterable, Mapping, Sequence
from typing import Protocol

from groq import (
    APIError,
    APITimeoutError,
    AuthenticationError,
    PermissionDeniedError,
    RateLimitError,
)
from groq.types.chat import ChatCompletionMessageParam

from app.core.exceptions import (
    LLMAuthenticationError,
    LLMMalformedResponseError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.domains.evaluation.errors import EvaluationConfigurationError
from app.domains.evaluation.model_execution import (
    LLMExecutionRequest,
    LLMExecutionResult,
    TokenUsage,
)
from app.domains.evaluation.types import EvaluationValue


class _Message(Protocol):
    content: str | None


class _Choice(Protocol):
    message: _Message


class _Usage(Protocol):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class _CompletionResponse(Protocol):
    choices: Sequence[_Choice]
    model: str
    usage: _Usage | None


class _CompletionsResource(Protocol):
    async def create(
        self,
        *,
        messages: Iterable[ChatCompletionMessageParam],
        model: str,
        temperature: float,
        max_completion_tokens: int,
    ) -> _CompletionResponse: ...


class _ChatResource(Protocol):
    completions: _CompletionsResource


class GroqAsyncClient(Protocol):
    chat: _ChatResource


def _json_compatible(value: EvaluationValue) -> object:
    if isinstance(value, Mapping):
        return {key: _json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_compatible(item) for item in value]
    return value


def _render_test_input(test_input: EvaluationValue) -> str:
    if isinstance(test_input, str):
        return test_input
    return json.dumps(
        _json_compatible(test_input),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _messages_for(request: LLMExecutionRequest) -> list[ChatCompletionMessageParam]:
    messages: list[ChatCompletionMessageParam] = []
    if request.model_config.system_wrapper is not None:
        messages.append(
            {
                "role": "system",
                "content": request.model_config.system_wrapper,
            }
        )
    messages.extend(
        [
            {"role": "user", "content": request.player_prompt},
            {"role": "user", "content": _render_test_input(request.test_input)},
        ]
    )
    return messages


def _retry_after_seconds(error: RateLimitError) -> float | None:
    raw_value = error.response.headers.get("retry-after")
    if raw_value is None:
        return None
    try:
        value = float(raw_value)
    except ValueError:
        return None
    return value if value >= 0 else None


class GroqProvider:
    """Groq adapter for the provider-neutral asynchronous execution port."""

    def __init__(self, client: GroqAsyncClient) -> None:
        self._client = client

    async def generate(self, request: LLMExecutionRequest) -> LLMExecutionResult:
        try:
            response = await self._client.chat.completions.create(
                messages=_messages_for(request),
                model=request.model_config.model_id,
                temperature=request.model_config.temperature,
                max_completion_tokens=request.model_config.max_output_tokens,
            )
        except (AuthenticationError, PermissionDeniedError):
            raise LLMAuthenticationError(
                "The model provider rejected backend authentication."
            ) from None
        except RateLimitError as error:
            raise LLMRateLimitError(
                retry_after_seconds=_retry_after_seconds(error),
            ) from None
        except APITimeoutError:
            raise LLMTimeoutError("The model provider request timed out.") from None
        except APIError:
            raise LLMProviderError("The model provider request failed.") from None
        except Exception:
            raise LLMProviderError("The model provider request failed.") from None

        try:
            choice = response.choices[0]
            output_text = choice.message.content
            model_id = response.model
        except (AttributeError, IndexError, TypeError):
            raise LLMMalformedResponseError(
                "The model provider returned an unusable response."
            ) from None
        if (
            not isinstance(output_text, str)
            or not isinstance(model_id, str)
            or not model_id.strip()
        ):
            raise LLMMalformedResponseError("The model provider returned an unusable response.")

        usage = None
        if response.usage is not None:
            try:
                usage = TokenUsage(
                    input_tokens=response.usage.prompt_tokens,
                    output_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                )
            except (AttributeError, EvaluationConfigurationError, TypeError, ValueError):
                raise LLMMalformedResponseError(
                    "The model provider returned invalid usage information."
                ) from None

        return LLMExecutionResult(
            output_text=output_text,
            model_id=model_id,
            usage=usage,
        )
