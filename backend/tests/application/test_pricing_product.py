"""The new package participates in the existing product pipeline, including replay."""

import asyncio
import os

import pytest

from app.application.challenges.access import ChallengeAccessService
from app.application.challenges.errors import ChallengeLockedError
from app.application.challenges.execution_guard import (
    ApplicationExecutionService,
    application_submit_result_from_payload,
    application_submit_result_to_payload,
)
from app.application.challenges.models import SubmitChallengeCommand
from app.application.challenges.submit_challenge import SubmitChallengeUseCase
from app.domains.challenges.models import ChallengeType
from app.domains.execution import ChallengeExecutorResolver
from app.domains.execution.application import ApplicationChallengeExecutor
from app.domains.scoring.service import ScoringService
from app.infrastructure.application import (
    LocalWorkspaceFactory,
    PlaywrightApplicationEvaluator,
    StarterProjectRepository,
)
from app.infrastructure.challenges.application_fixtures import APPLICATION_CHALLENGES
from app.infrastructure.challenges.in_memory_repository import (
    CONTROL_CHALLENGES,
    InMemoryChallengeRepository,
)
from tests.application.test_application_flow import (
    OWNER,
    AllowAllAccess,
    IdempotencyCoordinator,
    IdempotentInMemorySubmissions,
)
from tests.fakes.application import FakeCodingAgent, solution_output
from tests.fakes.pricing import pricing_output
from tests.fakes.tokenization import FakePromptTokenCounter


def test_pricing_unlock_scoring_xp_replay_and_screenshot_payload(tmp_path):
    async def exercise():
        packages = StarterProjectRepository()
        coordinator = IdempotencyCoordinator()
        store = IdempotentInMemorySubmissions(coordinator)
        reader = InMemoryChallengeRepository((*CONTROL_CHALLENGES, *APPLICATION_CHALLENGES))
        access = ChallengeAccessService(reader, store)
        with pytest.raises(ChallengeLockedError):
            await access.require_access(APPLICATION_CHALLENGES[1], OWNER)
        agent = FakeCodingAgent(solution_output())
        executor = ApplicationChallengeExecutor(
            agent,
            LocalWorkspaceFactory(packages, tmp_path),
            PlaywrightApplicationEvaluator(os.getenv("APPLICATION_BROWSER_CHANNEL") or None),
            packages,
        )
        resolver = ChallengeExecutorResolver({ChallengeType.APPLICATION: executor})
        guard = ApplicationExecutionService(
            coordinator,
            run_cooldown_seconds=10,
            submit_cooldown_seconds=20,
            stale_after_seconds=180,
        )
        # Prior CONTROL completion is covered by the existing access suite.
        hero = SubmitChallengeUseCase(
            reader, resolver, FakePromptTokenCounter(42), ScoringService(), store, AllowAllAccess()
        )
        await hero.execute(SubmitChallengeCommand("responsive-hero", "Arrange the hero.", OWNER))
        unlocked = await access.require_access(APPLICATION_CHALLENGES[1], OWNER)
        assert unlocked.status.value == "available"
        agent.output_text = pricing_output()
        pricing = SubmitChallengeUseCase(
            reader,
            resolver,
            FakePromptTokenCounter(42),
            ScoringService(),
            store,
            access,
            application_execution_service=guard,
            application_submission_repository=store,
        )
        command = SubmitChallengeCommand(
            "pricing-grid", "Arrange the plans.", OWNER, "pricing-submit-key"
        )
        result = await pricing.execute(command)
        assert (result.evaluation_score, result.stars, result.xp_earned, result.total_xp) == (
            100,
            3,
            175,
            350,
        )
        assert result.completed
        replay = await pricing.execute(command)
        assert replay == result and len(agent.tasks) == 2
        assert len(store.submissions) == 2
        assert store.progress[(OWNER, "control-pricing-grid")].attempts == 1
        assert (
            application_submit_result_from_payload(application_submit_result_to_payload(result))
            == result
        )
        assert (
            await access.require_access(APPLICATION_CHALLENGES[1], OWNER)
        ).status.value == "mastered"
        assert list(tmp_path.iterdir()) == []

    asyncio.run(exercise())
