"""Golden comparison: the executor-based Run/Submit path must match the pre-refactor flow.

`reference_run` and `reference_submit` reproduce the original direct
LLMProvider → EvaluationEngine → ScoringService composition from before
TextChallengeExecutor existed. Both paths receive identical fake outputs.
"""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.application.challenges.models import (
    RunChallengeCommand,
    RunChallengeResult,
    SubmitChallengeCommand,
    SubmitChallengeResult,
    VisibleTestRunResult,
)
from app.application.challenges.run_challenge import RunChallengeUseCase
from app.application.challenges.submit_challenge import SubmitChallengeUseCase
from app.domains.challenges.models import ChallengeType, PlayableChallenge
from app.domains.evaluation.engine import EvaluationEngine
from app.domains.evaluation.model_execution import LLMExecutionRequest, LLMExecutionResult
from app.domains.execution import UnsupportedChallengeTypeError
from app.domains.progression import XPRewardConfiguration
from app.domains.scoring.service import ScoringService
from app.domains.submissions import Submission
from app.infrastructure.challenges.control_fixtures import CONTROL_HIDDEN_TEST_SUITES
from app.infrastructure.challenges.in_memory_hidden_test_repository import (
    InMemoryHiddenTestRepository,
)
from app.infrastructure.challenges.in_memory_repository import (
    CONTROL_CHALLENGES,
    EXACT_OUTPUT_CHALLENGE,
    InMemoryChallengeRepository,
)
from app.infrastructure.submissions import InMemorySubmissionRepository
from tests.fakes.execution import text_executor_resolver
from tests.fakes.llm import FakeLLMProvider
from tests.fakes.tokenization import FakePromptTokenCounter

OWNER = "e21d712d-1268-4246-975d-9cd29c15d966"
PROMPT = "Follow the challenge objective exactly."


class AllowAllAccess:
    async def require_access(self, _playable, _owner_user_id) -> None:
        return None


class TrackingHiddenReader(InMemoryHiddenTestRepository):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[tuple[str, str]] = []

    async def get_for_version(self, challenge_id: str, version_id: str):
        self.requests.append((challenge_id, version_id))
        return await super().get_for_version(challenge_id, version_id)


def provider_for(texts: list[str]) -> FakeLLMProvider:
    return FakeLLMProvider(
        *(LLMExecutionResult(output_text=text, model_id="fake") for text in texts)
    )


def patterns(expected: list[str]) -> dict[str, list[str]]:
    return {
        "all_correct": expected,
        "all_wrong": ["WRONG"] * len(expected),
        "alternating": [text if index % 2 == 0 else "WRONG" for index, text in enumerate(expected)],
        "first_wrong": ["WRONG", *expected[1:]],
    }


async def reference_run(playable: PlayableChallenge, provider) -> RunChallengeResult:
    version = playable.version
    outputs = {}
    for test_case in version.visible_test_cases:
        execution = await provider.generate(
            LLMExecutionRequest(PROMPT, test_case.input, version.model_config)
        )
        outputs[test_case.id] = execution.output_text
    evaluation = EvaluationEngine.with_builtin_graders().evaluate_batch(
        version.visible_test_cases, outputs
    )
    grades = {result.test_case_id: result.grade for result in evaluation.test_results}
    return RunChallengeResult(
        challenge_id=playable.challenge.id,
        challenge_slug=playable.challenge.slug,
        challenge_version_id=version.version_id,
        test_results=tuple(
            VisibleTestRunResult(
                test_id=case.id,
                input=case.input,
                expected_output=case.expected_output,
                actual_output=outputs[case.id],
                passed=grades[case.id].passed,
                failure_reason=grades[case.id].failure_reason,
            )
            for case in version.visible_test_cases
        ),
        passed_count=evaluation.passed_count,
        total_count=evaluation.total_count,
        accuracy=evaluation.accuracy,
    )


async def reference_submit(
    playable: PlayableChallenge, provider, repository: InMemorySubmissionRepository
) -> tuple[SubmitChallengeResult, Submission]:
    version = playable.version
    suite = CONTROL_HIDDEN_TEST_SUITES[playable.challenge.id]
    outputs = {}
    for test_case in suite.test_cases:
        execution = await provider.generate(
            LLMExecutionRequest(PROMPT, test_case.input, version.model_config)
        )
        outputs[test_case.id] = execution.output_text
    evaluation = EvaluationEngine.with_builtin_graders().evaluate_batch(suite.test_cases, outputs)
    scoring = ScoringService().calculate(
        prompt_tokens=42, accuracy=evaluation.accuracy, configuration=version.scoring_config
    )
    submission = Submission(
        id="reference",
        challenge_id=playable.challenge.id,
        challenge_version_id=version.version_id,
        user_id=OWNER,
        prompt=PROMPT,
        prompt_tokens=scoring.prompt_tokens,
        passed_tests=evaluation.passed_count,
        total_tests=evaluation.total_count,
        accuracy=evaluation.accuracy,
        efficiency=scoring.efficiency,
        final_score=scoring.final_score,
        stars=scoring.stars,
        model_identifier=version.model_config.model_id,
        model_configuration_version=version.model_config.configuration_version,
        created_at=datetime.now(UTC),
    )
    progression = await repository.save_with_progression(
        submission, difficulty=version.difficulty, xp_configuration=XPRewardConfiguration()
    )
    result = SubmitChallengeResult(
        challenge_slug=playable.challenge.slug,
        challenge_version_id=version.version_id,
        passed_count=evaluation.passed_count,
        total_count=evaluation.total_count,
        accuracy=evaluation.accuracy,
        prompt_tokens=scoring.prompt_tokens,
        efficiency=scoring.efficiency,
        final_score=scoring.final_score,
        stars=scoring.stars,
        xp_earned=progression.xp_earned,
        total_xp=progression.total_xp,
        best_score=progression.progress.best_score,
        best_stars=progression.progress.best_stars,
        completed=progression.progress.completed_at is not None,
    )
    return result, submission


def run_use_case(playable: PlayableChallenge, provider) -> RunChallengeUseCase:
    return RunChallengeUseCase(
        challenge_reader=InMemoryChallengeRepository((playable,)),
        executor_resolver=text_executor_resolver(provider),
        access_service=AllowAllAccess(),
    )


def submit_use_case(
    playable: PlayableChallenge, provider, repository, hidden_reader=None
) -> SubmitChallengeUseCase:
    return SubmitChallengeUseCase(
        challenge_reader=InMemoryChallengeRepository((playable,)),
        executor_resolver=text_executor_resolver(provider, hidden_reader),
        prompt_token_counter=FakePromptTokenCounter(42),
        scoring_service=ScoringService(),
        submission_repository=repository,
        access_service=AllowAllAccess(),
    )


CASES = [
    (playable, name)
    for playable in CONTROL_CHALLENGES
    for name in ("all_correct", "all_wrong", "alternating", "first_wrong")
]


@pytest.mark.parametrize(("playable", "pattern"), CASES)
def test_run_matches_pre_refactor_flow(playable: PlayableChallenge, pattern: str) -> None:
    expected = [str(case.expected_output) for case in playable.version.visible_test_cases]
    texts = patterns(expected)[pattern]
    command = RunChallengeCommand(challenge_slug=playable.challenge.slug, player_prompt=PROMPT)

    actual = asyncio.run(run_use_case(playable, provider_for(texts)).execute(command))
    reference = asyncio.run(reference_run(playable, provider_for(texts)))

    assert actual == reference


@pytest.mark.parametrize(("playable", "pattern"), CASES)
def test_submit_matches_pre_refactor_flow(playable: PlayableChallenge, pattern: str) -> None:
    suite = CONTROL_HIDDEN_TEST_SUITES[playable.challenge.id]
    expected = [str(case.expected_output) for case in suite.test_cases]
    texts = patterns(expected)[pattern]
    command = SubmitChallengeCommand(
        challenge_slug=playable.challenge.slug, player_prompt=PROMPT, owner_user_id=OWNER
    )
    actual_repository = InMemorySubmissionRepository()
    reference_repository = InMemorySubmissionRepository()

    actual = asyncio.run(
        submit_use_case(playable, provider_for(texts), actual_repository).execute(command)
    )
    reference, reference_submission = asyncio.run(
        reference_submit(playable, provider_for(texts), reference_repository)
    )

    assert actual == reference
    persisted = actual_repository.submissions[0]
    assert replace(persisted, id="reference", created_at=reference_submission.created_at) == (
        reference_submission
    )
    assert [(t.reason, t.amount) for t in actual_repository.xp_transactions] == [
        (t.reason, t.amount) for t in reference_repository.xp_transactions
    ]
    assert actual_repository.progress.keys() == reference_repository.progress.keys()
    for key, progress in actual_repository.progress.items():
        reference_progress = reference_repository.progress[key]
        assert (progress.best_score, progress.best_stars, progress.attempts) == (
            reference_progress.best_score,
            reference_progress.best_stars,
            reference_progress.attempts,
        )


def test_exact_output_golden_values_are_unchanged() -> None:
    """Hard-coded values produced by the pre-refactor implementation."""
    texts = ["YES", "NO", "YES", "YES", "NO", "NO"]  # every hidden case correct
    result = asyncio.run(
        submit_use_case(
            EXACT_OUTPUT_CHALLENGE, provider_for(texts), InMemorySubmissionRepository()
        ).execute(
            SubmitChallengeCommand(
                challenge_slug="exact-output", player_prompt=PROMPT, owner_user_id=OWNER
            )
        )
    )
    assert (result.passed_count, result.total_count, result.accuracy) == (6, 6, 100.0)
    assert (result.prompt_tokens, result.efficiency, result.final_score) == (42, 100.0, 100.0)
    assert (result.stars, result.xp_earned, result.total_xp) == (3, 175, 175)
    assert result.completed is True


def unsupported(challenge_type: ChallengeType) -> PlayableChallenge:
    return replace(
        EXACT_OUTPUT_CHALLENGE,
        version=replace(EXACT_OUTPUT_CHALLENGE.version, challenge_type=challenge_type),
    )


@pytest.mark.parametrize("challenge_type", [ChallengeType.IMAGE])
def test_run_fails_explicitly_for_unsupported_type_without_execution(
    challenge_type: ChallengeType,
) -> None:
    provider = provider_for(["YES"])
    with pytest.raises(UnsupportedChallengeTypeError):
        asyncio.run(
            run_use_case(unsupported(challenge_type), provider).execute(
                RunChallengeCommand(challenge_slug="exact-output", player_prompt=PROMPT)
            )
        )
    assert provider.requests == []


@pytest.mark.parametrize("challenge_type", [ChallengeType.IMAGE])
def test_submit_fails_explicitly_for_unsupported_type_without_side_effects(
    challenge_type: ChallengeType,
) -> None:
    provider = provider_for(["YES"])
    repository = InMemorySubmissionRepository()
    hidden_reader = TrackingHiddenReader()
    with pytest.raises(UnsupportedChallengeTypeError):
        asyncio.run(
            submit_use_case(
                unsupported(challenge_type), provider, repository, hidden_reader
            ).execute(
                SubmitChallengeCommand(
                    challenge_slug="exact-output", player_prompt=PROMPT, owner_user_id=OWNER
                )
            )
        )
    assert provider.requests == []
    assert hidden_reader.requests == []
    assert repository.submissions == []


def test_run_never_reads_hidden_suite() -> None:
    hidden_reader = TrackingHiddenReader()
    use_case = RunChallengeUseCase(
        challenge_reader=InMemoryChallengeRepository((EXACT_OUTPUT_CHALLENGE,)),
        executor_resolver=text_executor_resolver(provider_for(["YES"]), hidden_reader),
        access_service=AllowAllAccess(),
    )
    asyncio.run(
        use_case.execute(RunChallengeCommand(challenge_slug="exact-output", player_prompt=PROMPT))
    )
    assert hidden_reader.requests == []
