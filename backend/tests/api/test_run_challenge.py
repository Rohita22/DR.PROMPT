import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_run_challenge_use_case
from app.application.challenges.access import ChallengeAccessService
from app.application.challenges.run_challenge import RunChallengeUseCase
from app.core.exceptions import (
    LLMOutputTruncatedError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMStructuredResponseError,
)
from app.domains.challenges.models import ChallengeType
from app.domains.evaluation.model_execution import LLMExecutionRequest, LLMExecutionResult
from app.domains.evaluation.ports import LLMProvider
from app.infrastructure.challenges.in_memory_repository import (
    EXACT_OUTPUT_CHALLENGE,
    InMemoryChallengeRepository,
)
from app.infrastructure.submissions import InMemorySubmissionRepository
from app.main import app
from tests.fakes.execution import text_executor_resolver
from tests.fakes.llm import FakeLLMProvider


class RateLimitedProvider:
    async def generate(self, request: LLMExecutionRequest) -> LLMExecutionResult:
        del request
        raise LLMRateLimitError()


class FailingProvider:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def generate(self, request: LLMExecutionRequest) -> LLMExecutionResult:
        del request
        raise self.error


def make_use_case(
    provider: LLMProvider,
    repository: InMemoryChallengeRepository | None = None,
) -> RunChallengeUseCase:
    challenge_reader = repository or InMemoryChallengeRepository()
    return RunChallengeUseCase(
        challenge_reader=challenge_reader,
        executor_resolver=text_executor_resolver(provider),
        access_service=ChallengeAccessService(
            challenge_reader,
            InMemorySubmissionRepository(),
        ),
    )


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


def test_run_endpoint_returns_typed_visible_test_feedback_without_hidden_data() -> None:
    provider = FakeLLMProvider(
        LLMExecutionResult(output_text="YES", model_id="fake"),
        LLMExecutionResult(output_text="YES", model_id="fake"),
        LLMExecutionResult(output_text="YES", model_id="fake"),
    )
    app.dependency_overrides[get_run_challenge_use_case] = lambda: make_use_case(provider)

    response = TestClient(app).post(
        "/api/v1/challenges/exact-output/run",
        json={"prompt": "Return YES for available services, otherwise return NO."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["challenge"] == "exact-output"
    assert payload["challenge_id"] == "control-exact-output"
    assert payload["version"] == "1"
    assert payload["passed"] == 2
    assert payload["total"] == 3
    assert payload["accuracy"] == 66.67
    assert payload["tests"][0] == {
        "id": "visible-1",
        "input": "The status page says all systems are operational.",
        "expected": "YES",
        "actual": "YES",
        "passed": True,
        "failure_reason": None,
    }
    assert payload["tests"][1]["failure_reason"] == "output_mismatch"
    serialized = json.dumps(payload).lower()
    assert "hidden" not in serialized
    assert "raw_response" not in serialized
    assert "api_key" not in serialized


def test_run_endpoint_maps_unknown_challenge_to_consistent_404() -> None:
    provider = FakeLLMProvider(LLMExecutionResult(output_text="YES", model_id="fake"))
    use_case = make_use_case(provider, InMemoryChallengeRepository(challenges=()))
    app.dependency_overrides[get_run_challenge_use_case] = lambda: use_case

    response = TestClient(app).post(
        "/api/v1/challenges/missing/run",
        json={"prompt": "Return YES or NO."},
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "challenge_not_found",
            "message": "Published challenge 'missing' was not found.",
        }
    }
    assert provider.requests == []


def test_run_endpoint_rejects_blank_prompt_at_http_boundary() -> None:
    provider = FakeLLMProvider(LLMExecutionResult(output_text="YES", model_id="fake"))
    app.dependency_overrides[get_run_challenge_use_case] = lambda: make_use_case(provider)

    response = TestClient(app).post(
        "/api/v1/challenges/exact-output/run",
        json={"prompt": "   "},
    )

    assert response.status_code == 422
    assert provider.requests == []


def test_run_endpoint_preserves_safe_provider_rate_limit_error() -> None:
    app.dependency_overrides[get_run_challenge_use_case] = lambda: make_use_case(
        RateLimitedProvider()
    )

    response = TestClient(app).post(
        "/api/v1/challenges/exact-output/run",
        json={"prompt": "Return YES or NO."},
    )

    assert response.status_code == 429
    assert response.json() == {
        "error": {
            "code": "llm_rate_limit_error",
            "message": "The model provider rate limit was reached.",
        }
    }


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (LLMRefusalError("The coding agent declined the requested task."), "agent_refused"),
        (
            LLMOutputTruncatedError("The coding agent response exceeded its output limit."),
            "output_truncated",
        ),
        (
            LLMStructuredResponseError("The coding agent returned an invalid structured response."),
            "agent_invalid_response",
        ),
    ],
)
def test_run_endpoint_preserves_safe_agent_failure_categories(error: Exception, code: str) -> None:
    app.dependency_overrides[get_run_challenge_use_case] = lambda: make_use_case(
        FailingProvider(error)
    )

    response = TestClient(app).post(
        "/api/v1/challenges/exact-output/run",
        json={"prompt": "Return YES or NO."},
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == code


def test_run_endpoint_reports_unsupported_challenge_type_without_execution() -> None:
    playable = replace(
        EXACT_OUTPUT_CHALLENGE,
        version=replace(EXACT_OUTPUT_CHALLENGE.version, challenge_type=ChallengeType.IMAGE),
    )
    provider = FakeLLMProvider(LLMExecutionResult(output_text="YES", model_id="fake"))
    app.dependency_overrides[get_run_challenge_use_case] = lambda: make_use_case(
        provider, InMemoryChallengeRepository((playable,))
    )

    response = TestClient(app).post(
        "/api/v1/challenges/exact-output/run",
        json={"prompt": "Return YES or NO."},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "unsupported_challenge_type"
    assert provider.requests == []


def test_run_and_submit_openapi_contracts_are_unchanged() -> None:
    schemas = TestClient(app).get("/openapi.json").json()["components"]["schemas"]

    assert set(schemas["RunChallengeResponse"]["properties"]) == {
        "challenge",
        "challenge_id",
        "version",
        "passed",
        "total",
        "accuracy",
        "tests",
    }
    assert set(schemas["SubmitChallengeResponse"]["properties"]) == {
        "challenge",
        "version",
        "passed",
        "total",
        "accuracy",
        "prompt_tokens",
        "efficiency",
        "score",
        "stars",
        "xp_earned",
        "total_xp",
        "best_score",
        "best_stars",
        "completed",
    }
    for text_schema in ("RunChallengeResponse", "SubmitChallengeResponse"):
        assert "challenge_type" not in json.dumps(schemas[text_schema])
