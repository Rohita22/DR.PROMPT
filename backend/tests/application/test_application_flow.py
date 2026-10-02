"""End-to-end APPLICATION Run/Submit through the real use cases, offline.

Real disposable workspaces and edit validation; a fake coding agent and a fake
browser evaluator keep the flow deterministic and free of provider calls.
"""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import fields
from pathlib import Path

import pytest

from app.application.challenges.access import ChallengeAccessService
from app.application.challenges.errors import (
    ChallengeAuthenticationRequiredError,
    ChallengeLockedError,
    PromptTooLongError,
)
from app.application.challenges.execution_guard import (
    ApplicationExecutionService,
    ApplicationExecutionStart,
)
from app.application.challenges.models import (
    ApplicationRunResult,
    ApplicationSubmitResult,
    RunChallengeCommand,
    SubmitChallengeCommand,
)
from app.application.challenges.run_challenge import RunChallengeUseCase
from app.application.challenges.submit_challenge import SubmitChallengeUseCase
from app.core.exceptions import ApplicationRateLimitError, LLMTimeoutError
from app.domains.challenges.models import ChallengeType
from app.domains.evaluation.engine import EvaluationEngine
from app.domains.evaluation.model_execution import LLMExecutionResult
from app.domains.execution import (
    AgentStatus,
    BuildStatus,
    ChallengeExecutorResolver,
    TextChallengeExecutor,
)
from app.domains.execution.application import ApplicationChallengeExecutor
from app.domains.progression import XPAwardReason
from app.domains.scoring.service import ScoringService
from app.infrastructure.application import LocalWorkspaceFactory, StarterProjectRepository
from app.infrastructure.challenges.application_fixtures import (
    RESPONSIVE_HERO_CHALLENGE,
    RESPONSIVE_HERO_CONFIG,
)
from app.infrastructure.challenges.in_memory_hidden_test_repository import (
    InMemoryHiddenTestRepository,
)
from app.infrastructure.challenges.in_memory_repository import (
    CONTROL_CHALLENGES,
    InMemoryChallengeRepository,
)
from app.infrastructure.submissions import InMemorySubmissionRepository
from tests.fakes.application import (
    STARTER_ROOT,
    FakeCodingAgent,
    FakeEvaluator,
    solution_output,
    starter_layouts,
    tree_digest,
)
from tests.fakes.llm import FakeLLMProvider
from tests.fakes.tokenization import FakePromptTokenCounter

OWNER = "7c1b7d63-3f6e-4a51-9a0b-2e9b8a6f9e11"
PROMPT = "Use a two-column grid for the hero on desktop and stack it below 760px."


class AllowAllAccess:
    async def require_access(self, _playable, _owner_user_id) -> None:
        return None


def resolver(agent, evaluator, tmp_path: Path) -> ChallengeExecutorResolver:
    return ChallengeExecutorResolver(
        {
            ChallengeType.TEXT: TextChallengeExecutor(
                FakeLLMProvider(LLMExecutionResult("unused", "fake")),
                EvaluationEngine.with_builtin_graders(),
                InMemoryHiddenTestRepository(),
            ),
            ChallengeType.APPLICATION: ApplicationChallengeExecutor(
                agent,
                LocalWorkspaceFactory(StarterProjectRepository(), temp_root=tmp_path),
                evaluator,
                StarterProjectRepository(),
            ),
        }
    )


def repository(*extra) -> InMemoryChallengeRepository:
    return InMemoryChallengeRepository((*CONTROL_CHALLENGES, RESPONSIVE_HERO_CHALLENGE, *extra))


def submissions() -> InMemorySubmissionRepository:
    return InMemorySubmissionRepository({"control-responsive-hero": "responsive-hero"})


def submit_use_case(agent, evaluator, tmp_path, store, tokens=42, access=None):
    return SubmitChallengeUseCase(
        challenge_reader=repository(),
        executor_resolver=resolver(agent, evaluator, tmp_path),
        prompt_token_counter=FakePromptTokenCounter(tokens),
        scoring_service=ScoringService(),
        submission_repository=store,
        access_service=access or AllowAllAccess(),
    )


def submit(use_case) -> ApplicationSubmitResult:
    return asyncio.run(
        use_case.execute(
            SubmitChallengeCommand(
                challenge_slug="responsive-hero", player_prompt=PROMPT, owner_user_id=OWNER
            )
        )
    )


def test_run_returns_screenshots_changes_build_and_only_visible_checks(tmp_path: Path) -> None:
    before = tree_digest(STARTER_ROOT)
    agent = FakeCodingAgent(solution_output())
    use_case = RunChallengeUseCase(
        challenge_reader=repository(),
        executor_resolver=resolver(agent, FakeEvaluator(), tmp_path),
        access_service=AllowAllAccess(),
    )

    result = asyncio.run(
        use_case.execute(
            RunChallengeCommand(challenge_slug="responsive-hero", player_prompt=PROMPT)
        )
    )

    assert isinstance(result, ApplicationRunResult)
    assert [c.check_id for c in result.checks] == list(RESPONSIVE_HERO_CONFIG.visible_checks)
    assert all(c.passed and c.label != "hidden" for c in result.checks)
    assert result.evaluation_score == 100.0
    assert result.build.status is BuildStatus.PASSED
    assert result.changes.agent_status is AgentStatus.APPLIED
    assert [s.viewport for s in result.screenshots] == ["desktop", "mobile"]
    assert not {c.check_id for c in result.checks} & set(
        RESPONSIVE_HERO_CONFIG.hidden_checks
    ) - set(RESPONSIVE_HERO_CONFIG.visible_checks)
    assert agent.tasks[0].player_prompt == PROMPT
    assert tree_digest(STARTER_ROOT) == before
    assert list(tmp_path.iterdir()) == []


def test_application_challenge_uses_existing_progression_locks(tmp_path: Path) -> None:
    agent = FakeCodingAgent(solution_output())
    store = submissions()
    access = ChallengeAccessService(repository(), store)
    use_case = RunChallengeUseCase(repository(), resolver(agent, FakeEvaluator(), tmp_path), access)

    with pytest.raises(ChallengeAuthenticationRequiredError):
        asyncio.run(use_case.execute(RunChallengeCommand("responsive-hero", PROMPT)))
    with pytest.raises(ChallengeLockedError):
        asyncio.run(use_case.execute(RunChallengeCommand("responsive-hero", PROMPT, OWNER)))
    with pytest.raises(ChallengeLockedError):
        submit(submit_use_case(agent, FakeEvaluator(), tmp_path, store, access=access))
    assert agent.tasks == []


def test_submit_scores_persists_and_awards_xp_through_existing_systems(tmp_path: Path) -> None:
    store = submissions()
    result = submit(
        submit_use_case(FakeCodingAgent(solution_output()), FakeEvaluator(), tmp_path, store)
    )

    assert isinstance(result, ApplicationSubmitResult)
    assert (result.passed_count, result.total_count) == (9, 9)
    assert (result.evaluation_score, result.efficiency, result.final_score) == (100.0, 100, 100.0)
    assert (result.stars, result.xp_earned, result.total_xp) == (3, 175, 175)
    assert result.completed and result.best_stars == 3
    assert result.agent_status is AgentStatus.APPLIED
    assert result.screenshot is not None and result.screenshot.viewport == "desktop"

    [persisted] = store.submissions
    assert persisted.challenge_id == "control-responsive-hero"
    assert persisted.challenge_version_id == "1"
    assert persisted.user_id == OWNER
    assert (persisted.passed_tests, persisted.total_tests) == (9, 9)
    assert persisted.accuracy == 100.0  # stores the normalized evaluation score
    assert persisted.final_score == 100.0 and persisted.stars == 3
    assert persisted.model_identifier == "openai/gpt-oss-20b"
    assert persisted.model_configuration_version == "responsive-hero-agent-v2"
    assert {t.reason for t in store.xp_transactions} == {
        XPAwardReason.FIRST_COMPLETION,
        XPAwardReason.TWO_STAR,
        XPAwardReason.THREE_STAR,
    }


def test_partial_functional_result_scores_below_the_star_threshold(tmp_path: Path) -> None:
    store = submissions()
    result = submit(
        submit_use_case(
            FakeCodingAgent(solution_output()), FakeEvaluator(starter_layouts()), tmp_path, store
        )
    )
    assert (result.passed_count, result.total_count) == (5, 9)
    assert result.evaluation_score == pytest.approx(500 / 9)
    assert result.final_score == 64.44  # 55.56 * 0.8 + 100 * 0.2
    assert (result.stars, result.xp_earned, result.completed) == (0, 0, False)


def test_rejected_agent_output_is_a_scored_zero_not_an_error(tmp_path: Path) -> None:
    store = submissions()
    result = submit(
        submit_use_case(FakeCodingAgent("no json here"), FakeEvaluator(), tmp_path, store)
    )
    assert (result.passed_count, result.evaluation_score, result.stars) == (0, 0.0, 0)
    assert result.agent_status is AgentStatus.REJECTED
    assert result.screenshot is None
    assert len(store.submissions) == 1


def test_prompt_over_the_hard_limit_never_reaches_the_agent(tmp_path: Path) -> None:
    agent = FakeCodingAgent(solution_output())
    store = submissions()
    with pytest.raises(PromptTooLongError):
        submit(submit_use_case(agent, FakeEvaluator(), tmp_path, store, tokens=401))
    assert agent.tasks == [] and store.submissions == []


class RejectingCoordinator:
    @asynccontextmanager
    async def start(self, _scope, *, kind, **_kwargs):
        raise ApplicationRateLimitError(7, kind.value)
        yield ApplicationExecutionStart()  # pragma: no cover


def test_local_cooldown_rejection_creates_no_workspace_or_provider_call(tmp_path: Path) -> None:
    agent = FakeCodingAgent(solution_output())
    guard = ApplicationExecutionService(
        RejectingCoordinator(),
        run_cooldown_seconds=10,
        submit_cooldown_seconds=20,
        stale_after_seconds=180,
    )
    use_case = RunChallengeUseCase(
        challenge_reader=repository(),
        executor_resolver=resolver(agent, FakeEvaluator(), tmp_path),
        access_service=AllowAllAccess(),
        application_execution_service=guard,
    )

    with pytest.raises(ApplicationRateLimitError) as rejected:
        asyncio.run(use_case.execute(RunChallengeCommand("responsive-hero", PROMPT, OWNER)))

    assert rejected.value.retry_after_seconds == 7
    assert agent.tasks == []
    assert list(tmp_path.iterdir()) == []


def test_submit_result_cannot_represent_hidden_check_details(tmp_path: Path) -> None:
    result = submit(
        submit_use_case(
            FakeCodingAgent(solution_output()), FakeEvaluator(), tmp_path, submissions()
        )
    )
    names = {field.name for field in fields(result)}
    assert not names & {"checks", "check_results", "tests", "build", "log", "changed_files"}
    serialized = repr(result)
    for check_id in RESPONSIVE_HERO_CONFIG.hidden_checks:
        assert check_id not in serialized


class IdempotencyCoordinator:
    def __init__(self) -> None:
        self.active: set[str] = set()
        self.completed: dict[tuple[str, str, str], ApplicationSubmitResult] = {}
        self.reservations: dict[str, tuple[str, str, str]] = {}

    @asynccontextmanager
    async def start(
        self,
        scope,
        *,
        kind,
        cooldown_seconds,
        stale_after_seconds,
        idempotency_key_hash=None,
    ):
        del kind, cooldown_seconds, stale_after_seconds
        key = (scope.user_id, scope.challenge_version_id, idempotency_key_hash or "")
        if key in self.completed:
            yield ApplicationExecutionStart(replay=self.completed[key])
            return
        reservation = f"reservation-{len(self.reservations) + 1}"
        self.reservations[reservation] = key
        self.active.add(scope.user_id)
        try:
            yield ApplicationExecutionStart(reservation_id=reservation)
        except BaseException:
            self.reservations.pop(reservation, None)
            raise
        finally:
            self.active.discard(scope.user_id)

    def complete(self, reservation_id: str, result: ApplicationSubmitResult) -> None:
        self.completed[self.reservations.pop(reservation_id)] = result


class IdempotentInMemorySubmissions(InMemorySubmissionRepository):
    def __init__(self, coordinator: IdempotencyCoordinator) -> None:
        super().__init__(
            {"control-responsive-hero": "responsive-hero", "control-pricing-grid": "pricing-grid"}
        )
        self.coordinator = coordinator

    async def save_application_with_progression(self, submission, **kwargs):
        result = await super().save_application_with_progression(submission, **kwargs)
        self.coordinator.complete(kwargs["reservation_id"], result)
        return result


class FailOnceCodingAgent(FakeCodingAgent):
    async def apply_instructions(self, task):
        self.tasks.append(task)
        if len(self.tasks) == 1:
            raise TimeoutError("provider timeout")
        return await super().apply_instructions(task)


def test_duplicate_application_submit_is_replayed_without_side_effects(tmp_path: Path) -> None:
    coordinator = IdempotencyCoordinator()
    guard = ApplicationExecutionService(
        coordinator,
        run_cooldown_seconds=0,
        submit_cooldown_seconds=0,
        stale_after_seconds=180,
    )
    store = IdempotentInMemorySubmissions(coordinator)
    agent = FakeCodingAgent(solution_output())
    use_case = SubmitChallengeUseCase(
        challenge_reader=repository(),
        executor_resolver=resolver(agent, FakeEvaluator(), tmp_path),
        prompt_token_counter=FakePromptTokenCounter(42),
        scoring_service=ScoringService(),
        submission_repository=store,
        access_service=AllowAllAccess(),
        application_execution_service=guard,
        application_submission_repository=store,
    )
    command = SubmitChallengeCommand(
        "responsive-hero", PROMPT, OWNER, idempotency_key="submit-action-123"
    )

    first = asyncio.run(use_case.execute(command))
    replay = asyncio.run(use_case.execute(command))

    assert replay == first
    assert len(agent.tasks) == 1
    assert len(store.submissions) == 1
    assert store.progress[(OWNER, "control-responsive-hero")].attempts == 1
    assert sum(item.amount for item in store.xp_transactions) == 175

    other_user = "195fd5c5-cae4-46d1-a901-828e9c986ab5"
    asyncio.run(
        use_case.execute(
            SubmitChallengeCommand(
                "responsive-hero",
                PROMPT,
                other_user,
                idempotency_key="submit-action-123",
            )
        )
    )
    assert len(agent.tasks) == 2
    assert len(store.submissions) == 2
    assert store.progress[(other_user, "control-responsive-hero")].attempts == 1


def test_failed_infrastructure_submit_key_can_retry_without_authoritative_side_effects(
    tmp_path: Path,
) -> None:
    coordinator = IdempotencyCoordinator()
    guard = ApplicationExecutionService(
        coordinator,
        run_cooldown_seconds=0,
        submit_cooldown_seconds=0,
        stale_after_seconds=180,
    )
    store = IdempotentInMemorySubmissions(coordinator)
    agent = FailOnceCodingAgent(solution_output())
    use_case = SubmitChallengeUseCase(
        challenge_reader=repository(),
        executor_resolver=resolver(agent, FakeEvaluator(), tmp_path),
        prompt_token_counter=FakePromptTokenCounter(42),
        scoring_service=ScoringService(),
        submission_repository=store,
        access_service=AllowAllAccess(),
        application_execution_service=guard,
        application_submission_repository=store,
    )
    command = SubmitChallengeCommand(
        "responsive-hero", PROMPT, OWNER, idempotency_key="retry-action-123"
    )

    with pytest.raises(LLMTimeoutError):
        asyncio.run(use_case.execute(command))
    assert store.submissions == [] and store.xp_transactions == []

    result = asyncio.run(use_case.execute(command))
    assert isinstance(result, ApplicationSubmitResult)
    assert len(store.submissions) == 1
    assert len(agent.tasks) == 3  # failing call + superclass records the successful call
    assert list(tmp_path.iterdir()) == []
