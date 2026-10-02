import asyncio
import difflib
import logging
import time

from app.core.exceptions import LLMTimeoutError
from app.domains.application.checks import (
    ApplicationCheckRegistry,
    ApplicationCheckResult,
    ApplicationFacts,
    CheckDefinition,
)
from app.domains.application.edits import FileEdit, parse_agent_edits
from app.domains.application.errors import AgentOutputError
from app.domains.application.models import ApplicationChallengeConfig, SourceFile
from app.domains.application.ports import (
    AgentTask,
    ApplicationEvaluator,
    ApplicationPackageLoader,
    CodingAgent,
    WorkspaceFactory,
)
from app.domains.application.sandbox import (
    ApplicationSandbox,
    DisabledApplicationSandbox,
    ExecutionMode,
    SandboxUnavailableError,
)
from app.domains.challenges.models import ChallengeType
from app.domains.evaluation.results import (
    FailureReason,
    GradeResult,
    SafeDiagnostic,
    TestEvaluationResult,
)
from app.domains.execution.errors import UnsupportedChallengeTypeError
from app.domains.execution.models import (
    AgentStatus,
    BuildArtifact,
    BuildStatus,
    ChallengeExecutionRequest,
    ChallengeExecutionResult,
    ChangedFile,
    ChangedFilesArtifact,
    ExecutionArtifact,
)


class ApplicationChallengeExecutor:
    """APPLICATION family: coding agent edits a disposable starter copy, then checks run.

    Flow per attempt: fresh workspace → agent (player prompt + editable files only) →
    strict edit validation → allowlisted writes → predefined build → browser measurement →
    deterministic checks → workspace destroyed. `evaluation_score` = passed / total × 100.
    """

    def __init__(
        self,
        coding_agent: CodingAgent,
        workspaces: WorkspaceFactory,
        evaluator: ApplicationEvaluator,
        packages: ApplicationPackageLoader,
        sandbox: ApplicationSandbox | None = None,
    ) -> None:
        self._sandbox = sandbox or DisabledApplicationSandbox()
        self._coding_agent = coding_agent
        self._workspaces = workspaces
        self._evaluator = evaluator
        self._packages = packages
        self._checks = ApplicationCheckRegistry()

    async def execute_admin(self, request: ChallengeExecutionRequest) -> ChallengeExecutionResult:
        config = self._config(request)
        checks = tuple(dict.fromkeys((*config.visible_checks, *config.hidden_checks)))
        return await self._execute(request, config, checks)

    async def execute_visible(
        self,
        request: ChallengeExecutionRequest,
    ) -> ChallengeExecutionResult:
        config = self._config(request)
        return await self._execute(request, config, config.visible_checks)

    async def execute_hidden(
        self,
        request: ChallengeExecutionRequest,
    ) -> ChallengeExecutionResult:
        config = self._config(request)
        return await self._execute(request, config, config.hidden_checks)

    @staticmethod
    def _config(request: ChallengeExecutionRequest) -> ApplicationChallengeConfig:
        version = request.playable.version
        if version.challenge_type is not ChallengeType.APPLICATION:
            raise UnsupportedChallengeTypeError(str(version.challenge_type))
        assert version.application_config is not None  # enforced by ChallengeVersion
        return version.application_config

    async def _execute(
        self,
        request: ChallengeExecutionRequest,
        config: ApplicationChallengeConfig,
        check_ids: tuple[str, ...],
    ) -> ChallengeExecutionResult:
        package = self._packages.validate(config)
        checks = package.selected_checks(check_ids)
        started = time.monotonic()
        executable = config.execution_mode == ExecutionMode.SANDBOXED_EXECUTABLE
        if executable and not (await self._sandbox.capability()).available:
            raise SandboxUnavailableError()
        with self._workspaces.create(config.starter_project, config.editable_files) as workspace:
            starter_html = workspace.read_text(config.page_source)
            originals = {path: workspace.read_text(path) for path in config.editable_files}
            task = AgentTask(
                player_prompt=request.player_prompt,
                files=tuple(SourceFile(path, content) for path, content in originals.items()),
                model_config=request.playable.version.model_config,
            )
            agent_started = time.monotonic()
            try:
                agent_result = await asyncio.wait_for(
                    self._coding_agent.apply_instructions(task),
                    timeout=config.limits.agent_timeout_seconds,
                )
            except TimeoutError:
                raise LLMTimeoutError("The coding agent did not finish in time.") from None

            logging.getLogger(__name__).info(
                "application_agent", extra={"duration_seconds": time.monotonic() - agent_started}
            )
            try:
                edits = parse_agent_edits(agent_result.output_text, originals, config.limits)
            except AgentOutputError as error:
                return _rejected_result(checks, error)

            for edit in edits:
                workspace.write_text(edit.path, edit.content)

            protected_unchanged = workspace.modified_paths() <= set(config.editable_files)
            result_html = workspace.read_text(config.page_source)
            inspection = (
                await self._sandbox.inspect(workspace, config, package, checks)
                if executable
                else await self._evaluator.inspect(workspace, config, package)
            )
            logging.getLogger(__name__).info(
                "application_execution",
                extra={
                    "execution_mode": config.execution_mode.value,
                    "total_seconds": time.monotonic() - started,
                    "exit_category": inspection.build.status.value,
                },
            )

        outcomes = self._checks.evaluate(
            checks,
            ApplicationFacts(
                build_succeeded=inspection.build.status is BuildStatus.PASSED,
                protected_files_unchanged=protected_unchanged,
                starter_html=starter_html,
                result_html=result_html,
                layouts=inspection.layouts,
                behavior_results=inspection.behavior_results,
            ),
        )
        artifacts: tuple[ExecutionArtifact, ...] = (
            ChangedFilesArtifact(AgentStatus.APPLIED, None, _changed_files(originals, edits)),
            inspection.build,
            *inspection.screenshots,
        )
        return _result(outcomes, artifacts)


def _changed_files(
    originals: dict[str, str], edits: tuple[FileEdit, ...]
) -> tuple[ChangedFile, ...]:
    changed = []
    for edit in edits:
        additions = deletions = 0
        diff = difflib.unified_diff(
            originals[edit.path].splitlines(), edit.content.splitlines(), lineterm="", n=0
        )
        for line in diff:
            if line.startswith("+") and not line.startswith("+++"):
                additions += 1
            elif line.startswith("-") and not line.startswith("---"):
                deletions += 1
        if additions or deletions:
            changed.append(ChangedFile(edit.path, additions, deletions))
    return tuple(changed)


def _rejected_result(
    checks: tuple[CheckDefinition, ...], error: AgentOutputError
) -> ChallengeExecutionResult:
    """A rejected edit set is a failed attempt: every check fails and nothing is built."""
    outcomes = tuple(
        ApplicationCheckResult(
            check.id, False, check.label, "Not evaluated because the agent's edits were rejected."
        )
        for check in checks
    )
    artifacts: tuple[ExecutionArtifact, ...] = (
        ChangedFilesArtifact(AgentStatus.REJECTED, error.message, ()),
        BuildArtifact(BuildStatus.SKIPPED, ""),
    )
    return _result(outcomes, artifacts, failure=FailureReason.AGENT_OUTPUT_REJECTED)


def _result(
    outcomes: tuple[ApplicationCheckResult, ...],
    artifacts: tuple[ExecutionArtifact, ...],
    failure: FailureReason = FailureReason.CHECK_FAILED,
) -> ChallengeExecutionResult:
    passed = sum(outcome.passed for outcome in outcomes)
    return ChallengeExecutionResult(
        evaluation_score=passed / len(outcomes) * 100.0,
        passed_checks=passed,
        total_checks=len(outcomes),
        check_results=tuple(
            TestEvaluationResult(
                test_case_id=outcome.check_id,
                label=outcome.label,
                grade=(
                    GradeResult(passed=True)
                    if outcome.passed
                    else GradeResult(
                        passed=False,
                        failure_reason=failure,
                        diagnostic=SafeDiagnostic(
                            code=failure.value,
                            message=outcome.message or "Check failed.",
                        ),
                    )
                ),
            )
            for outcome in outcomes
        ),
        artifacts=artifacts,
    )
