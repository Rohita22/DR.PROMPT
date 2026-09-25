import asyncio
from dataclasses import fields, replace

import pytest

from app.application.challenges.access import ChallengeAccessService
from app.application.challenges.errors import PromptTooLongError
from app.application.challenges.models import (
    SubmitChallengeCommand,
    SubmitChallengeResult,
)
from app.application.challenges.submit_challenge import SubmitChallengeUseCase
from app.core.exceptions import LLMProviderError, PersistenceError
from app.domains.challenges.errors import ChallengeNotFoundError
from app.domains.challenges.models import PlayableChallenge
from app.domains.evaluation.engine import EvaluationEngine
from app.domains.evaluation.errors import (
    HiddenTestSuiteNotFoundError,
    HiddenTestSuiteVersionMismatchError,
)
from app.domains.evaluation.model_execution import LLMExecutionRequest, LLMExecutionResult
from app.domains.evaluation.test_cases import HiddenTestSuite
from app.domains.scoring.configuration import (
    EfficiencyThresholds,
    EfficiencyTier,
    ScoringConfiguration,
    StarThresholds,
)
from app.domains.scoring.service import ScoringService
from app.domains.submissions import Submission
from app.infrastructure.challenges.in_memory_hidden_test_repository import (
    EXACT_OUTPUT_HIDDEN_TEST_SUITE,
    InMemoryHiddenTestRepository,
)
from app.infrastructure.challenges.in_memory_repository import (
    EXACT_OUTPUT_CHALLENGE,
    InMemoryChallengeRepository,
)
from app.infrastructure.submissions import InMemorySubmissionRepository
from tests.fakes.llm import FakeLLMProvider
from tests.fakes.tokenization import FakePromptTokenCounter

OWNER_USER_ID = "e21d712d-1268-4246-975d-9cd29c15d966"


class TrackingChallengeReader:
    def __init__(self, playable: PlayableChallenge | None) -> None:
        self.playable = playable
        self.requested_slugs: list[str] = []

    async def get_by_slug(self, slug: str) -> PlayableChallenge | None:
        self.requested_slugs.append(slug)
        return self.playable

    async def list_published(self, _track=None) -> tuple[PlayableChallenge, ...]:
        return (self.playable,) if self.playable is not None else ()


class TrackingHiddenTestSuiteReader:
    def __init__(self, suite: HiddenTestSuite | None) -> None:
        self.suite = suite
        self.requests: list[tuple[str, str]] = []

    async def get_for_version(
        self,
        challenge_id: str,
        challenge_version_id: str,
    ) -> HiddenTestSuite | None:
        self.requests.append((challenge_id, challenge_version_id))
        return self.suite


class FailingProvider:
    def __init__(self) -> None:
        self.requests: list[LLMExecutionRequest] = []

    async def generate(self, request: LLMExecutionRequest) -> LLMExecutionResult:
        self.requests.append(request)
        raise LLMProviderError("The model provider request failed.")


def submit_use_case(
    challenge_reader: TrackingChallengeReader,
    hidden_reader: TrackingHiddenTestSuiteReader,
    provider: FakeLLMProvider | FailingProvider,
    token_counter: FakePromptTokenCounter | None = None,
    submission_repository: InMemorySubmissionRepository | None = None,
) -> SubmitChallengeUseCase:
    progression_repository = submission_repository or InMemorySubmissionRepository()
    return SubmitChallengeUseCase(
        challenge_reader=challenge_reader,
        hidden_test_suite_reader=hidden_reader,
        llm_provider=provider,
        evaluation_engine=EvaluationEngine.with_builtin_graders(),
        prompt_token_counter=token_counter or FakePromptTokenCounter(42),
        scoring_service=ScoringService(),
        submission_repository=progression_repository,
        access_service=ChallengeAccessService(challenge_reader, progression_repository),
    )


def test_hidden_repository_is_separate_and_bound_to_exact_version() -> None:
    public_repository = InMemoryChallengeRepository()
    hidden_repository = InMemoryHiddenTestRepository()
    playable = asyncio.run(public_repository.get_by_slug("exact-output"))

    assert playable is EXACT_OUTPUT_CHALLENGE
    assert not hasattr(playable, "hidden_test_suite")
    assert not hasattr(playable.version, "hidden_test_cases")
    assert (
        asyncio.run(hidden_repository.get_for_version("control-exact-output", "1"))
        is EXACT_OUTPUT_HIDDEN_TEST_SUITE
    )
    assert asyncio.run(hidden_repository.get_for_version("control-exact-output", "2")) is None
    assert len(EXACT_OUTPUT_HIDDEN_TEST_SUITE.test_cases) == 6


def test_submit_executes_each_hidden_test_and_returns_only_aggregates() -> None:
    challenge_reader = TrackingChallengeReader(EXACT_OUTPUT_CHALLENGE)
    hidden_reader = TrackingHiddenTestSuiteReader(EXACT_OUTPUT_HIDDEN_TEST_SUITE)
    outputs = ("YES", "NO", "NO", "YES", "NO", "YES")
    provider = FakeLLMProvider(
        *(LLMExecutionResult(output_text=output, model_id="fake") for output in outputs)
    )
    counter = FakePromptTokenCounter(42)
    submissions = InMemorySubmissionRepository()
    prompt = "Return exactly YES when currently available, otherwise exactly NO."

    result = asyncio.run(
        submit_use_case(
            challenge_reader,
            hidden_reader,
            provider,
            counter,
            submissions,
        ).execute(
            SubmitChallengeCommand(
                challenge_slug="exact-output",
                player_prompt=prompt,
                owner_user_id=OWNER_USER_ID,
            )
        )
    )

    assert challenge_reader.requested_slugs == ["exact-output"]
    assert counter.requests == [(prompt, EXACT_OUTPUT_CHALLENGE.version.model_config.model_id)]
    assert hidden_reader.requests == [("control-exact-output", "1")]
    assert len(provider.requests) == 6
    assert [request.player_prompt for request in provider.requests] == [prompt] * 6
    assert [request.test_input for request in provider.requests] == [
        test.input for test in EXACT_OUTPUT_HIDDEN_TEST_SUITE.test_cases
    ]
    assert all(
        request.model_config is EXACT_OUTPUT_CHALLENGE.version.model_config
        for request in provider.requests
    )
    assert result == SubmitChallengeResult(
        challenge_slug="exact-output",
        challenge_version_id="1",
        passed_count=4,
        total_count=6,
        accuracy=pytest.approx(200 / 3),
        prompt_tokens=42,
        efficiency=100,
        final_score=73.33,
        stars=0,
        xp_earned=0,
        total_xp=0,
        best_score=73.33,
        best_stars=0,
        completed=False,
    )
    assert {field.name for field in fields(result)} == {
        "challenge_slug",
        "challenge_version_id",
        "passed_count",
        "total_count",
        "accuracy",
        "prompt_tokens",
        "efficiency",
        "final_score",
        "stars",
        "xp_earned",
        "total_xp",
        "best_score",
        "best_stars",
        "completed",
    }
    assert len(submissions.submissions) == 1
    persisted = submissions.submissions[0]
    assert persisted.prompt == prompt
    assert persisted.user_id == OWNER_USER_ID
    assert persisted.prompt_tokens == result.prompt_tokens
    assert persisted.passed_tests == result.passed_count
    assert persisted.total_tests == result.total_count
    assert persisted.accuracy == result.accuracy
    assert persisted.efficiency == result.efficiency
    assert persisted.final_score == result.final_score
    assert persisted.stars == result.stars
    assert persisted.model_identifier == EXACT_OUTPUT_CHALLENGE.version.model_config.model_id
    assert (
        persisted.model_configuration_version
        == EXACT_OUTPUT_CHALLENGE.version.model_config.configuration_version
    )


def test_submit_updates_progress_and_awards_only_new_milestones() -> None:
    submissions = InMemorySubmissionRepository()
    correct_outputs = ("YES", "NO", "YES", "YES", "NO", "NO")

    def execute(outputs: tuple[str, ...], token_count: int) -> SubmitChallengeResult:
        provider = FakeLLMProvider(
            *(LLMExecutionResult(output_text=value, model_id="fake") for value in outputs)
        )
        return asyncio.run(
            submit_use_case(
                TrackingChallengeReader(EXACT_OUTPUT_CHALLENGE),
                TrackingHiddenTestSuiteReader(EXACT_OUTPUT_HIDDEN_TEST_SUITE),
                provider,
                FakePromptTokenCounter(token_count),
                submissions,
            ).execute(
                SubmitChallengeCommand(
                    challenge_slug="exact-output",
                    player_prompt="Return exactly YES or NO.",
                    owner_user_id=OWNER_USER_ID,
                )
            )
        )

    one_star = execute(("YES", "NO", "YES", "YES", "NO", "YES"), 42)
    repeated_one_star = execute(("YES", "NO", "YES", "YES", "NO", "YES"), 42)
    two_star = execute(correct_outputs, 61)
    three_star = execute(correct_outputs, 42)
    repeated_three_star = execute(correct_outputs, 42)

    assert one_star.xp_earned == 100
    assert repeated_one_star.xp_earned == 0
    assert two_star.xp_earned == 25
    assert three_star.xp_earned == 50
    assert repeated_three_star.xp_earned == 0
    assert three_star.total_xp == 175
    assert repeated_three_star.total_xp == 175
    assert repeated_three_star.best_stars == 3
    assert repeated_three_star.best_score == 100
    assert repeated_three_star.completed is True
    progress = submissions.progress[(OWNER_USER_ID, "control-exact-output")]
    assert progress.attempts == 5
    assert len(submissions.submissions) == 5
    assert len(submissions.xp_transactions) == 3


def test_submit_counts_prompt_before_hidden_loading_and_rejects_over_limit() -> None:
    hidden_reader = TrackingHiddenTestSuiteReader(EXACT_OUTPUT_HIDDEN_TEST_SUITE)
    provider = FakeLLMProvider(LLMExecutionResult(output_text="YES", model_id="fake"))
    counter = FakePromptTokenCounter(301)
    submissions = InMemorySubmissionRepository()
    prompt = "A prompt whose authoritative fake count exceeds the configured limit."

    with pytest.raises(PromptTooLongError) as error:
        asyncio.run(
            submit_use_case(
                TrackingChallengeReader(EXACT_OUTPUT_CHALLENGE),
                hidden_reader,
                provider,
                counter,
                submissions,
            ).execute(
                SubmitChallengeCommand(
                    challenge_slug="exact-output",
                    player_prompt=prompt,
                    owner_user_id=OWNER_USER_ID,
                )
            )
        )

    assert counter.requests == [(prompt, EXACT_OUTPUT_CHALLENGE.version.model_config.model_id)]
    assert error.value.actual_tokens == 301
    assert error.value.maximum_tokens == 300
    assert hidden_reader.requests == []
    assert provider.requests == []
    assert submissions.submissions == []
    assert submissions.progress == {}
    assert submissions.xp_transactions == []


def test_submit_honors_custom_challenge_scoring_configuration() -> None:
    custom_scoring = ScoringConfiguration(
        accuracy_weight=0.5,
        efficiency_weight=0.5,
        efficiency_thresholds=EfficiencyThresholds(
            tiers=(EfficiencyTier(100, 50),),
            score_above_max=25,
        ),
        star_thresholds=StarThresholds(50, 75, 100, three_star_max_prompt_tokens=20),
    )
    custom_version = replace(
        EXACT_OUTPUT_CHALLENGE.version,
        scoring_config=custom_scoring,
    )
    custom_challenge = replace(EXACT_OUTPUT_CHALLENGE, version=custom_version)
    provider = FakeLLMProvider(
        *(
            LLMExecutionResult(output_text=value, model_id="fake")
            for value in (
                "YES",
                "NO",
                "YES",
                "YES",
                "NO",
                "NO",
            )
        )
    )

    result = asyncio.run(
        submit_use_case(
            TrackingChallengeReader(custom_challenge),
            TrackingHiddenTestSuiteReader(EXACT_OUTPUT_HIDDEN_TEST_SUITE),
            provider,
            FakePromptTokenCounter(42),
        ).execute(
            SubmitChallengeCommand(
                challenge_slug="exact-output",
                player_prompt="Return exactly YES or NO.",
                owner_user_id=OWNER_USER_ID,
            )
        )
    )

    assert result.accuracy == 100
    assert result.efficiency == 50
    assert result.final_score == 75
    assert result.stars == 2


def test_submit_rejects_suite_from_a_different_version_before_execution() -> None:
    mismatched_suite = HiddenTestSuite(
        challenge_version_id="2",
        test_cases=EXACT_OUTPUT_HIDDEN_TEST_SUITE.test_cases,
    )
    provider = FakeLLMProvider(LLMExecutionResult(output_text="YES", model_id="fake"))

    with pytest.raises(HiddenTestSuiteVersionMismatchError):
        asyncio.run(
            submit_use_case(
                TrackingChallengeReader(EXACT_OUTPUT_CHALLENGE),
                TrackingHiddenTestSuiteReader(mismatched_suite),
                provider,
            ).execute(
                SubmitChallengeCommand(
                    challenge_slug="exact-output",
                    player_prompt="Return YES or NO.",
                    owner_user_id=OWNER_USER_ID,
                )
            )
        )

    assert provider.requests == []


def test_submit_fails_predictably_when_hidden_suite_is_missing() -> None:
    provider = FakeLLMProvider(LLMExecutionResult(output_text="YES", model_id="fake"))

    with pytest.raises(HiddenTestSuiteNotFoundError):
        asyncio.run(
            submit_use_case(
                TrackingChallengeReader(EXACT_OUTPUT_CHALLENGE),
                TrackingHiddenTestSuiteReader(None),
                provider,
            ).execute(
                SubmitChallengeCommand(
                    challenge_slug="exact-output",
                    player_prompt="Return YES or NO.",
                    owner_user_id=OWNER_USER_ID,
                )
            )
        )

    assert provider.requests == []


def test_submit_unknown_challenge_does_not_request_hidden_suite() -> None:
    hidden_reader = TrackingHiddenTestSuiteReader(EXACT_OUTPUT_HIDDEN_TEST_SUITE)
    provider = FakeLLMProvider(LLMExecutionResult(output_text="YES", model_id="fake"))

    with pytest.raises(ChallengeNotFoundError, match="missing"):
        asyncio.run(
            submit_use_case(
                TrackingChallengeReader(None),
                hidden_reader,
                provider,
            ).execute(
                SubmitChallengeCommand(
                    challenge_slug="missing",
                    player_prompt="Return YES or NO.",
                    owner_user_id=OWNER_USER_ID,
                )
            )
        )

    assert hidden_reader.requests == []
    assert provider.requests == []


def test_submit_provider_failure_propagates_without_partial_grading() -> None:
    provider = FailingProvider()
    submissions = InMemorySubmissionRepository()

    with pytest.raises(LLMProviderError, match="provider request failed"):
        asyncio.run(
            submit_use_case(
                TrackingChallengeReader(EXACT_OUTPUT_CHALLENGE),
                TrackingHiddenTestSuiteReader(EXACT_OUTPUT_HIDDEN_TEST_SUITE),
                provider,
                submission_repository=submissions,
            ).execute(
                SubmitChallengeCommand(
                    challenge_slug="exact-output",
                    player_prompt="Return YES or NO.",
                    owner_user_id=OWNER_USER_ID,
                )
            )
        )

    assert len(provider.requests) == 1
    assert submissions.submissions == []
    assert submissions.progress == {}
    assert submissions.xp_transactions == []


class FailingSubmissionRepository:
    def __init__(self) -> None:
        self.attempts: list[Submission] = []

    async def save_with_progression(self, submission: Submission, **_kwargs: object) -> None:
        self.attempts.append(submission)
        raise PersistenceError("Database operation failed.")


def test_submit_persistence_failure_prevents_false_success() -> None:
    provider = FakeLLMProvider(
        *(
            LLMExecutionResult(output_text=value, model_id="fake")
            for value in ("YES", "NO", "YES", "YES", "NO", "NO")
        )
    )
    repository = FailingSubmissionRepository()
    challenge_reader = TrackingChallengeReader(EXACT_OUTPUT_CHALLENGE)

    with pytest.raises(PersistenceError, match="Database operation failed"):
        asyncio.run(
            SubmitChallengeUseCase(
                challenge_reader=challenge_reader,
                hidden_test_suite_reader=TrackingHiddenTestSuiteReader(
                    EXACT_OUTPUT_HIDDEN_TEST_SUITE
                ),
                llm_provider=provider,
                evaluation_engine=EvaluationEngine.with_builtin_graders(),
                prompt_token_counter=FakePromptTokenCounter(42),
                scoring_service=ScoringService(),
                submission_repository=repository,
                access_service=ChallengeAccessService(
                    challenge_reader,
                    InMemorySubmissionRepository(),
                ),
            ).execute(
                SubmitChallengeCommand(
                    challenge_slug="exact-output",
                    player_prompt="Return YES or NO.",
                    owner_user_id=OWNER_USER_ID,
                )
            )
        )

    assert len(repository.attempts) == 1


def test_two_authenticated_owners_create_differently_owned_submissions() -> None:
    submissions = InMemorySubmissionRepository()
    owners = (
        "7284f8ab-5d09-49cb-a312-553c71817590",
        "1aaad6a5-afd0-4f5e-8549-52073502d99a",
    )

    for owner in owners:
        provider = FakeLLMProvider(
            *(
                LLMExecutionResult(output_text=value, model_id="fake")
                for value in ("YES", "NO", "YES", "YES", "NO", "NO")
            )
        )
        asyncio.run(
            submit_use_case(
                TrackingChallengeReader(EXACT_OUTPUT_CHALLENGE),
                TrackingHiddenTestSuiteReader(EXACT_OUTPUT_HIDDEN_TEST_SUITE),
                provider,
                submission_repository=submissions,
            ).execute(
                SubmitChallengeCommand(
                    challenge_slug="exact-output",
                    player_prompt="Return YES or NO.",
                    owner_user_id=owner,
                )
            )
        )

    assert [submission.user_id for submission in submissions.submissions] == list(owners)
