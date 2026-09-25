import asyncio
from collections.abc import Iterable
from dataclasses import dataclass

import httpx
import pytest
from groq import APIError, APITimeoutError, AuthenticationError, RateLimitError
from groq.types.chat import ChatCompletionMessageParam

from app.core.exceptions import (
    LLMAuthenticationError,
    LLMMalformedResponseError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.domains.evaluation.configuration import ModelConfiguration
from app.domains.evaluation.model_execution import (
    LLMExecutionRequest,
    LLMExecutionResult,
    TokenUsage,
)
from app.domains.evaluation.ports import LLMProvider
from app.infrastructure.llm.groq_provider import GroqProvider
from tests.fakes.llm import FakeLLMProvider


@dataclass
class FakeUsage:
    prompt_tokens: int = 21
    completion_tokens: int = 4
    total_tokens: int = 25


@dataclass
class FakeMessage:
    content: str | None = "billing"


@dataclass
class FakeChoice:
    message: FakeMessage


@dataclass
class FakeResponse:
    choices: list[FakeChoice]
    model: str = "provider/model-actual"
    usage: FakeUsage | None = None


class FakeCompletions:
    def __init__(
        self,
        response: FakeResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response or FakeResponse(choices=[FakeChoice(FakeMessage())])
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def create(
        self,
        *,
        messages: Iterable[ChatCompletionMessageParam],
        model: str,
        temperature: float,
        max_completion_tokens: int,
    ) -> FakeResponse:
        self.calls.append(
            {
                "messages": list(messages),
                "model": model,
                "temperature": temperature,
                "max_completion_tokens": max_completion_tokens,
            }
        )
        if self.error is not None:
            raise self.error
        return self.response


class FakeChat:
    def __init__(self, completions: FakeCompletions) -> None:
        self.completions = completions


class FakeClient:
    def __init__(self, completions: FakeCompletions) -> None:
        self.chat = FakeChat(completions)


def execution_request(
    *, system_wrapper: str | None = "Challenge system wrapper"
) -> LLMExecutionRequest:
    return LLMExecutionRequest(
        player_prompt="Classify the supplied request using one label.",
        test_input="I need a copy of my invoice.",
        model_config=ModelConfiguration(
            model_id="provider/model-configured",
            temperature=0.25,
            max_output_tokens=64,
            configuration_version="config-v1",
            system_wrapper=system_wrapper,
        ),
    )


def run_provider(
    completions: FakeCompletions,
    request: LLMExecutionRequest | None = None,
) -> LLMExecutionResult:
    provider = GroqProvider(FakeClient(completions))
    return asyncio.run(provider.generate(request or execution_request()))


def test_maps_model_configuration_and_three_distinct_message_roles() -> None:
    completions = FakeCompletions()

    run_provider(completions)

    assert completions.calls == [
        {
            "messages": [
                {"role": "system", "content": "Challenge system wrapper"},
                {
                    "role": "user",
                    "content": "Classify the supplied request using one label.",
                },
                {"role": "user", "content": "I need a copy of my invoice."},
            ],
            "model": "provider/model-configured",
            "temperature": 0.25,
            "max_completion_tokens": 64,
        }
    ]


def test_omits_system_message_when_wrapper_is_absent() -> None:
    completions = FakeCompletions()

    run_provider(completions, execution_request(system_wrapper=None))

    messages = completions.calls[0]["messages"]
    assert messages == [
        {"role": "user", "content": "Classify the supplied request using one label."},
        {"role": "user", "content": "I need a copy of my invoice."},
    ]


def test_serializes_structured_test_input_canonically() -> None:
    completions = FakeCompletions()
    request = LLMExecutionRequest(
        player_prompt="Extract the fields.",
        test_input={"z": 2, "a": [True, None]},
        model_config=execution_request().model_config,
    )

    run_provider(completions, request)

    messages = completions.calls[0]["messages"]
    assert isinstance(messages, list)
    assert messages[-1] == {"role": "user", "content": '{"a":[true,null],"z":2}'}


def test_maps_generated_text_actual_model_and_token_usage_without_raw_response() -> None:
    raw_response = FakeResponse(
        choices=[FakeChoice(FakeMessage("technical"))],
        model="provider/model-actual",
        usage=FakeUsage(prompt_tokens=30, completion_tokens=2, total_tokens=32),
    )

    result = run_provider(FakeCompletions(response=raw_response))

    assert result == LLMExecutionResult(
        output_text="technical",
        model_id="provider/model-actual",
        usage=TokenUsage(input_tokens=30, output_tokens=2, total_tokens=32),
    )
    assert not hasattr(result, "raw_response")


def test_maps_absent_usage_to_none() -> None:
    result = run_provider(
        FakeCompletions(
            response=FakeResponse(
                choices=[FakeChoice(FakeMessage("billing"))],
                usage=None,
            )
        )
    )

    assert result.usage is None


def groq_status_error(error_type: type[AuthenticationError] | type[RateLimitError], status: int):
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(
        status,
        request=request,
        headers={"retry-after": "2.5"},
    )
    return error_type("provider detail containing secret-key", response=response, body=None)


def test_translates_authentication_failure_without_provider_detail() -> None:
    with pytest.raises(LLMAuthenticationError) as captured:
        run_provider(FakeCompletions(error=groq_status_error(AuthenticationError, 401)))

    assert "secret-key" not in captured.value.message
    assert captured.value.__cause__ is None


def test_translates_rate_limit_and_retains_safe_retry_timing() -> None:
    with pytest.raises(LLMRateLimitError) as captured:
        run_provider(FakeCompletions(error=groq_status_error(RateLimitError, 429)))

    assert captured.value.retry_after_seconds == 2.5
    assert "secret-key" not in captured.value.message


def test_translates_timeout_without_provider_detail() -> None:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")

    with pytest.raises(LLMTimeoutError) as captured:
        run_provider(FakeCompletions(error=APITimeoutError(request=request)))

    assert "timed out" in captured.value.message
    assert captured.value.__cause__ is None


def test_translates_unknown_client_failure_to_safe_generic_error() -> None:
    with pytest.raises(LLMProviderError) as captured:
        run_provider(FakeCompletions(error=RuntimeError("secret provider internals")))

    assert type(captured.value) is LLMProviderError
    assert "secret provider internals" not in captured.value.message


def test_translates_unknown_groq_api_failure_to_safe_generic_error() -> None:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    error = APIError("secret provider payload", request, body=None)

    with pytest.raises(LLMProviderError) as captured:
        run_provider(FakeCompletions(error=error))

    assert type(captured.value) is LLMProviderError
    assert "secret provider payload" not in captured.value.message


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse(choices=[]),
        FakeResponse(choices=[FakeChoice(FakeMessage(None))]),
    ],
)
def test_rejects_malformed_provider_response(response: FakeResponse) -> None:
    with pytest.raises(LLMMalformedResponseError, match="unusable response"):
        run_provider(FakeCompletions(response=response))


def test_reusable_fake_provider_records_provider_neutral_requests() -> None:
    expected = LLMExecutionResult(output_text="billing", model_id="fake-model")
    fake: LLMProvider = FakeLLMProvider(expected)
    request = execution_request()

    result = asyncio.run(fake.generate(request))

    assert result is expected
    assert isinstance(fake, FakeLLMProvider)
    assert fake.requests == [request]
