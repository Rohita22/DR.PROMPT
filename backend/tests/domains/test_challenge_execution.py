import asyncio
from dataclasses import replace

import pytest

from app.core.exceptions import LLMProviderError
from app.domains.challenges.models import ChallengeType, PlayableChallenge
from app.domains.evaluation.engine import EvaluationEngine
from app.domains.evaluation.errors import (
    HiddenTestSuiteNotFoundError,
    HiddenTestSuiteVersionMismatchError,
)
from app.domains.evaluation.model_execution import LLMExecutionRequest, LLMExecutionResult
from app.domains.evaluation.results import FailureReason
from app.domains.evaluation.test_cases import HiddenTestSuite
from app.domains.execution import (
    ChallengeExecutionError,
    ChallengeExecutionRequest,
    ChallengeExecutionResult,
    ChallengeExecutorResolver,
    TextChallengeExecutor,
    TextOutputArtifact,
    UnsupportedChallengeTypeError,
)
from app.infrastructure.challenges.application_fixtures import RESPONSIVE_HERO_CONFIG
from app.infrastructure.challenges.in_memory_hidden_test_repository import (
    EXACT_OUTPUT_HIDDEN_TEST_SUITE,
)
from app.infrastructure.challenges.in_memory_repository import EXACT_OUTPUT_CHALLENGE
from tests.fakes.llm import FakeLLMProvider

PROMPT = "Return exactly YES when currently available, otherwise exactly NO."


class TrackingHiddenReader:
    def __init__(self, suite: HiddenTestSuite | None) -> None:
        self.suite = suite
        self.requests: list[tuple[str, str]] = []

    async def get_for_version(self, challenge_id: str, version_id: str) -> HiddenTestSuite | None:
        self.requests.append((challenge_id, version_id))
        return self.suite


class FailingProvider:
    def __init__(self) -> None:
        self.requests: list[LLMExecutionRequest] = []

    async def generate(self, request: LLMExecutionRequest) -> LLMExecutionResult:
        self.requests.append(request)
        raise LLMProviderError("The model provider request failed.")


def outputs(*texts: str) -> FakeLLMProvider:
    return FakeLLMProvider(
        *(LLMExecutionResult(output_text=text, model_id="fake") for text in texts)
    )


def executor(provider, hidden_reader=None) -> TextChallengeExecutor:
    return TextChallengeExecutor(
        provider,
        EvaluationEngine.with_builtin_graders(),
        hidden_reader or TrackingHiddenReader(EXACT_OUTPUT_HIDDEN_TEST_SUITE),
    )


def request(playable: PlayableChallenge = EXACT_OUTPUT_CHALLENGE) -> ChallengeExecutionRequest:
    return ChallengeExecutionRequest(playable=playable, player_prompt=PROMPT)


def with_type(challenge_type: ChallengeType) -> PlayableChallenge:
    return replace(
        EXACT_OUTPUT_CHALLENGE,
        version=replace(
            EXACT_OUTPUT_CHALLENGE.version,
            challenge_type=challenge_type,
            application_config=(
                RESPONSIVE_HERO_CONFIG if challenge_type is ChallengeType.APPLICATION else None
            ),
        ),
    )


def test_control_fixtures_are_text_challenges() -> None:
    assert EXACT_OUTPUT_CHALLENGE.version.challenge_type is ChallengeType.TEXT


def test_visible_execution_runs_each_case_independently_and_grades_by_id() -> None:
    visible = EXACT_OUTPUT_CHALLENGE.version.visible_test_cases
    texts = (str(visible[0].expected_output), "WRONG", str(visible[2].expected_output))
    provider = outputs(*texts)
    hidden_reader = TrackingHiddenReader(EXACT_OUTPUT_HIDDEN_TEST_SUITE)

    result = asyncio.run(executor(provider, hidden_reader).execute_visible(request()))

    assert [item.test_input for item in provider.requests] == [case.input for case in visible]
    assert all(item.player_prompt == PROMPT for item in provider.requests)
    assert all(
        item.model_config is EXACT_OUTPUT_CHALLENGE.version.model_config
        for item in provider.requests
    )
    assert hidden_reader.requests == []
    assert result.artifacts == tuple(
        TextOutputArtifact(case.id, text) for case, text in zip(visible, texts, strict=True)
    )
    assert [check.test_case_id for check in result.check_results] == [case.id for case in visible]
    assert [check.grade.passed for check in result.check_results] == [True, False, True]
    assert result.check_results[1].grade.failure_reason is FailureReason.OUTPUT_MISMATCH
    assert (result.passed_checks, result.total_checks) == (2, 3)
    assert result.evaluation_score == pytest.approx(200 / 3)


def test_hidden_execution_loads_exact_version_suite_and_runs_every_case() -> None:
    provider = outputs(
        *(str(case.expected_output) for case in EXACT_OUTPUT_HIDDEN_TEST_SUITE.test_cases)
    )
    hidden_reader = TrackingHiddenReader(EXACT_OUTPUT_HIDDEN_TEST_SUITE)

    result = asyncio.run(executor(provider, hidden_reader).execute_hidden(request()))

    assert hidden_reader.requests == [("control-exact-output", "1")]
    assert [item.test_input for item in provider.requests] == [
        case.input for case in EXACT_OUTPUT_HIDDEN_TEST_SUITE.test_cases
    ]
    assert [artifact.test_case_id for artifact in result.artifacts] == [
        case.id for case in EXACT_OUTPUT_HIDDEN_TEST_SUITE.test_cases
    ]
    assert (result.passed_checks, result.total_checks, result.evaluation_score) == (6, 6, 100.0)


@pytest.mark.parametrize(
    ("suite", "error"),
    [
        (None, HiddenTestSuiteNotFoundError),
        (
            replace(EXACT_OUTPUT_HIDDEN_TEST_SUITE, challenge_version_id="2"),
            HiddenTestSuiteVersionMismatchError,
        ),
    ],
)
def test_hidden_execution_rejects_missing_or_mismatched_suite_before_model_calls(
    suite, error
) -> None:
    provider = outputs("YES")
    with pytest.raises(error, match="Challenge evaluation is unavailable"):
        asyncio.run(executor(provider, TrackingHiddenReader(suite)).execute_hidden(request()))
    assert provider.requests == []


@pytest.mark.parametrize("mode", ["execute_visible", "execute_hidden"])
def test_provider_errors_propagate_and_stop_execution(mode: str) -> None:
    provider = FailingProvider()
    with pytest.raises(LLMProviderError, match="provider request failed"):
        asyncio.run(getattr(executor(provider), mode)(request()))
    assert len(provider.requests) == 1


@pytest.mark.parametrize("challenge_type", [ChallengeType.APPLICATION, ChallengeType.IMAGE])
def test_text_executor_refuses_non_text_versions(challenge_type: ChallengeType) -> None:
    provider = outputs("YES")
    with pytest.raises(UnsupportedChallengeTypeError):
        asyncio.run(executor(provider).execute_visible(request(with_type(challenge_type))))
    assert provider.requests == []


def test_resolver_maps_text_and_fails_explicitly_for_unregistered_types() -> None:
    text_executor = executor(outputs("YES"))
    resolver = ChallengeExecutorResolver({ChallengeType.TEXT: text_executor})

    assert resolver.resolve(ChallengeType.TEXT) is text_executor
    for unsupported in (ChallengeType.APPLICATION, ChallengeType.IMAGE):
        with pytest.raises(UnsupportedChallengeTypeError, match=unsupported.value) as raised:
            resolver.resolve(unsupported)
        assert raised.value.code == "unsupported_challenge_type"


def test_resolver_state_is_per_instance_and_immune_to_source_mutation() -> None:
    source = {ChallengeType.TEXT: executor(outputs("YES"))}
    resolver = ChallengeExecutorResolver(source)
    empty = ChallengeExecutorResolver({})

    source.clear()

    assert resolver.resolve(ChallengeType.TEXT) is not None
    with pytest.raises(UnsupportedChallengeTypeError):
        empty.resolve(ChallengeType.TEXT)


def test_execution_contract_validates_request_and_normalized_result() -> None:
    with pytest.raises(ChallengeExecutionError):
        ChallengeExecutionRequest(playable=EXACT_OUTPUT_CHALLENGE, player_prompt="  ")
    for passed, total, score in ((1, 0, 0.0), (3, 2, 50.0), (1, 2, 100.5), (1, 2, -1.0)):
        with pytest.raises(ChallengeExecutionError):
            ChallengeExecutionResult(
                evaluation_score=score,
                passed_checks=passed,
                total_checks=total,
                check_results=(),
                artifacts=(),
            )
