import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.challenges import ChallengeAccessService
from app.application.challenges.errors import (
    ChallengeAuthenticationRequiredError,
    ChallengeLockedError,
)
from app.application.challenges.models import RunChallengeCommand, SubmitChallengeCommand
from app.application.challenges.run_challenge import RunChallengeUseCase
from app.application.challenges.submit_challenge import SubmitChallengeUseCase
from app.domains.challenges.models import ChallengeTrack, Difficulty
from app.domains.evaluation.engine import EvaluationEngine
from app.domains.evaluation.model_execution import LLMExecutionResult
from app.domains.progression import ChallengeStatus, XPRewardConfiguration
from app.domains.scoring.service import ScoringService
from app.domains.submissions import Submission
from app.infrastructure.challenges import (
    InMemoryChallengeRepository,
    InMemoryHiddenTestRepository,
)
from app.infrastructure.submissions import InMemorySubmissionRepository
from tests.fakes.llm import FakeLLMProvider
from tests.fakes.tokenization import FakePromptTokenCounter

USER_A = "11111111-1111-4111-8111-111111111111"
USER_B = "22222222-2222-4222-8222-222222222222"


def completion(user_id: str, challenge_id: str, stars: int = 1) -> Submission:
    return Submission(
        id=str(uuid4()),
        challenge_id=challenge_id,
        challenge_version_id="1",
        user_id=user_id,
        prompt="Follow the output rules.",
        prompt_tokens=5,
        passed_tests=5,
        total_tests=6,
        accuracy=83.33,
        efficiency=100,
        final_score=86.66,
        stars=stars,
        model_identifier="openai/gpt-oss-20b",
        model_configuration_version="1",
        created_at=datetime.now(UTC),
    )


def test_completion_immediately_unlocks_next_challenge_and_is_user_isolated() -> None:
    challenges = InMemoryChallengeRepository()
    progress = InMemorySubmissionRepository()
    access = ChallengeAccessService(challenges, progress)

    async def exercise() -> None:
        before = await access.list_track(ChallengeTrack.CONTROL, USER_A)
        assert before[1].status is ChallengeStatus.LOCKED
        await progress.save_with_progression(
            completion(USER_A, "control-exact-output"),
            difficulty=Difficulty.EASY,
            xp_configuration=XPRewardConfiguration(),
        )
        after = await access.list_track(ChallengeTrack.CONTROL, USER_A)
        other_user = await access.list_track(ChallengeTrack.CONTROL, USER_B)
        assert after[0].status is ChallengeStatus.COMPLETED
        assert after[1].status is ChallengeStatus.AVAILABLE
        assert other_user[1].status is ChallengeStatus.LOCKED

    asyncio.run(exercise())


def test_locked_submit_stops_before_token_count_model_or_persistence() -> None:
    challenges = InMemoryChallengeRepository()
    progress = InMemorySubmissionRepository()
    provider = FakeLLMProvider(
        LLMExecutionResult(output_text="YES", model_id="fake"),
        LLMExecutionResult(output_text="NO", model_id="fake"),
        LLMExecutionResult(output_text="YES", model_id="fake"),
    )
    token_counter = FakePromptTokenCounter(5)
    use_case = SubmitChallengeUseCase(
        challenge_reader=challenges,
        hidden_test_suite_reader=InMemoryHiddenTestRepository(),
        llm_provider=provider,
        evaluation_engine=EvaluationEngine.with_builtin_graders(),
        prompt_token_counter=token_counter,
        scoring_service=ScoringService(),
        submission_repository=progress,
        access_service=ChallengeAccessService(challenges, progress),
    )

    with pytest.raises(ChallengeLockedError):
        asyncio.run(
            use_case.execute(
                SubmitChallengeCommand(
                    challenge_slug="output-restrictions",
                    player_prompt="Return the final label only.",
                    owner_user_id=USER_A,
                )
            )
        )

    assert token_counter.requests == []
    assert provider.requests == []
    assert progress.submissions == []
    assert progress.progress == {}
    assert progress.xp_transactions == []


def test_anonymous_run_allows_first_challenge_but_rejects_later_challenge() -> None:
    challenges = InMemoryChallengeRepository()
    progress = InMemorySubmissionRepository()
    provider = FakeLLMProvider(
        LLMExecutionResult(output_text="YES", model_id="fake"),
        LLMExecutionResult(output_text="NO", model_id="fake"),
        LLMExecutionResult(output_text="YES", model_id="fake"),
    )
    use_case = RunChallengeUseCase(
        challenge_reader=challenges,
        llm_provider=provider,
        evaluation_engine=EvaluationEngine.with_builtin_graders(),
        access_service=ChallengeAccessService(challenges, progress),
    )

    first = asyncio.run(
        use_case.execute(
            RunChallengeCommand(
                challenge_slug="exact-output",
                player_prompt="Return YES or NO.",
            )
        )
    )
    assert first.total_count == 3

    with pytest.raises(ChallengeAuthenticationRequiredError):
        asyncio.run(
            use_case.execute(
                RunChallengeCommand(
                    challenge_slug="formatting-rules",
                    player_prompt="Return the required format.",
                )
            )
        )

    assert len(provider.requests) == 3
