import asyncio

import pytest

from app.application.challenges.models import RunChallengeCommand
from app.application.challenges.run_challenge import RunChallengeUseCase
from app.core.exceptions import LLMProviderError
from app.domains.challenges.errors import ChallengeNotFoundError
from app.domains.challenges.models import PlayableChallenge, PublicationState
from app.domains.evaluation.engine import EvaluationEngine
from app.domains.evaluation.model_execution import LLMExecutionRequest, LLMExecutionResult
from app.infrastructure.challenges.in_memory_repository import (
    EXACT_OUTPUT_CHALLENGE,
    InMemoryChallengeRepository,
)
from tests.fakes.llm import FakeLLMProvider


class TrackingChallengeReader:
    def __init__(self, playable: PlayableChallenge | None) -> None:
        self.playable = playable
        self.requested_slugs: list[str] = []

    def get_by_slug(self, slug: str) -> PlayableChallenge | None:
        self.requested_slugs.append(slug)
        return self.playable


class FailingProvider:
    def __init__(self) -> None:
        self.requests: list[LLMExecutionRequest] = []

    async def generate(self, request: LLMExecutionRequest) -> LLMExecutionResult:
        self.requests.append(request)
        raise LLMProviderError("The model provider request failed.")


def use_case(reader: TrackingChallengeReader, provider: FakeLLMProvider) -> RunChallengeUseCase:
    return RunChallengeUseCase(
        challenge_reader=reader,
        llm_provider=provider,
        evaluation_engine=EvaluationEngine.with_builtin_graders(),
    )


def test_repository_contains_one_published_control_challenge_with_three_visible_tests() -> None:
    repository = InMemoryChallengeRepository()
    playable = repository.get_by_slug("exact-output")

    assert playable is EXACT_OUTPUT_CHALLENGE
    assert playable.version.publication_state is PublicationState.PUBLISHED
    assert playable.challenge.track.value == "control"
    assert len(playable.version.visible_test_cases) == 3
    assert not hasattr(playable.version, "hidden_test_cases")
    assert repository.get_by_slug("another-challenge") is None


def test_run_executes_visible_tests_independently_and_grades_by_id() -> None:
    reader = TrackingChallengeReader(EXACT_OUTPUT_CHALLENGE)
    provider = FakeLLMProvider(
        LLMExecutionResult(output_text="YES", model_id="fake-model"),
        LLMExecutionResult(output_text="YES", model_id="fake-model"),
        LLMExecutionResult(output_text="YES", model_id="fake-model"),
    )
    prompt = "Respond with YES when available and NO when unavailable. Output one word only."

    result = asyncio.run(
        use_case(reader, provider).execute(
            RunChallengeCommand(challenge_slug="exact-output", player_prompt=prompt)
        )
    )

    assert reader.requested_slugs == ["exact-output"]
    assert len(provider.requests) == 3
    assert [request.player_prompt for request in provider.requests] == [prompt] * 3
    assert [request.test_input for request in provider.requests] == [
        test.input for test in EXACT_OUTPUT_CHALLENGE.version.visible_test_cases
    ]
    assert all(
        request.model_config is EXACT_OUTPUT_CHALLENGE.version.model_config
        for request in provider.requests
    )
    assert all(request.model_config.system_wrapper is not None for request in provider.requests)

    assert result.challenge_id == "control-exact-output"
    assert result.challenge_slug == "exact-output"
    assert result.challenge_version_id == "1"
    assert [test.test_id for test in result.test_results] == [
        "visible-1",
        "visible-2",
        "visible-3",
    ]
    assert [test.actual_output for test in result.test_results] == ["YES", "YES", "YES"]
    assert [test.expected_output for test in result.test_results] == ["YES", "NO", "YES"]
    assert [test.passed for test in result.test_results] == [True, False, True]
    assert result.passed_count == 2
    assert result.total_count == 3
    assert result.accuracy == pytest.approx(200 / 3)


def test_unknown_challenge_fails_before_model_execution() -> None:
    reader = TrackingChallengeReader(None)
    provider = FakeLLMProvider(LLMExecutionResult(output_text="YES", model_id="fake"))

    with pytest.raises(ChallengeNotFoundError, match="missing-challenge"):
        asyncio.run(
            use_case(reader, provider).execute(
                RunChallengeCommand(
                    challenge_slug="missing-challenge",
                    player_prompt="Return YES or NO.",
                )
            )
        )

    assert provider.requests == []


def test_provider_failure_propagates_instead_of_becoming_a_failed_answer() -> None:
    provider = FailingProvider()
    runner = RunChallengeUseCase(
        challenge_reader=TrackingChallengeReader(EXACT_OUTPUT_CHALLENGE),
        llm_provider=provider,
        evaluation_engine=EvaluationEngine.with_builtin_graders(),
    )

    with pytest.raises(LLMProviderError, match="provider request failed"):
        asyncio.run(
            runner.execute(
                RunChallengeCommand(
                    challenge_slug="exact-output",
                    player_prompt="Return YES or NO.",
                )
            )
        )

    assert len(provider.requests) == 1
