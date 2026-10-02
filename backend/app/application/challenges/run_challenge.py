from app.application.challenges.access import ChallengeAccessService
from app.application.challenges.execution_guard import (
    ApplicationExecutionScope,
    ApplicationExecutionService,
)
from app.application.challenges.models import (
    ApplicationCheckRunResult,
    ApplicationRunResult,
    RunChallengeCommand,
    RunChallengeResult,
    VisibleTestRunResult,
)
from app.domains.challenges.errors import ChallengeNotFoundError
from app.domains.challenges.models import ChallengeType, PlayableChallenge
from app.domains.challenges.ports import ChallengeReader
from app.domains.execution import (
    BuildArtifact,
    ChallengeExecutionRequest,
    ChallengeExecutionResult,
    ChallengeExecutorResolver,
    ChangedFilesArtifact,
    ScreenshotArtifact,
    TextOutputArtifact,
)


class RunChallengeUseCase:
    """Execute a challenge's visible evaluation and return detailed, debug-oriented feedback."""

    def __init__(
        self,
        challenge_reader: ChallengeReader,
        executor_resolver: ChallengeExecutorResolver,
        access_service: ChallengeAccessService,
        application_execution_service: ApplicationExecutionService | None = None,
    ) -> None:
        self._challenge_reader = challenge_reader
        self._executor_resolver = executor_resolver
        self._access_service = access_service
        self._application_execution_service = application_execution_service

    async def execute(
        self, command: RunChallengeCommand
    ) -> RunChallengeResult | ApplicationRunResult:
        playable = await self._challenge_reader.get_by_slug(command.challenge_slug)
        if playable is None:
            raise ChallengeNotFoundError(
                f"Published challenge '{command.challenge_slug}' was not found."
            )
        await self._access_service.require_access(playable, command.owner_user_id)

        version = playable.version
        if version.challenge_type is ChallengeType.APPLICATION:
            if self._application_execution_service is not None:
                if command.owner_user_id is None:
                    # Production access rejects this first; this protects direct construction.
                    raise ValueError("APPLICATION execution requires an authenticated owner.")
                scope = ApplicationExecutionScope(
                    user_id=command.owner_user_id,
                    challenge_id=playable.challenge.id,
                    challenge_slug=playable.challenge.slug,
                    challenge_version_id=version.version_id,
                )
                async with self._application_execution_service.run(scope):
                    execution = await self._execute(playable, command.player_prompt, visible=True)
            else:
                execution = await self._execute(playable, command.player_prompt, visible=True)
            return _application_result(playable, execution)
        execution = await self._execute(playable, command.player_prompt, visible=True)
        return _text_result(playable, execution)

    async def _execute(
        self, playable: PlayableChallenge, player_prompt: str, *, visible: bool
    ) -> ChallengeExecutionResult:
        executor = self._executor_resolver.resolve(playable.version.challenge_type)
        request = ChallengeExecutionRequest(playable=playable, player_prompt=player_prompt)
        return (
            await executor.execute_visible(request)
            if visible
            else await executor.execute_hidden(request)
        )


def _text_result(
    playable: PlayableChallenge,
    execution: ChallengeExecutionResult,
) -> RunChallengeResult:
    version = playable.version
    grades_by_id = {result.test_case_id: result.grade for result in execution.check_results}
    outputs_by_id = {
        artifact.test_case_id: artifact.output_text
        for artifact in execution.artifacts
        if isinstance(artifact, TextOutputArtifact)
    }
    visible_results = tuple(
        VisibleTestRunResult(
            test_id=test_case.id,
            input=test_case.input,
            expected_output=test_case.expected_output,
            actual_output=outputs_by_id[test_case.id],
            passed=grades_by_id[test_case.id].passed,
            failure_reason=grades_by_id[test_case.id].failure_reason,
        )
        for test_case in version.visible_test_cases
    )
    return RunChallengeResult(
        challenge_id=playable.challenge.id,
        challenge_slug=playable.challenge.slug,
        challenge_version_id=version.version_id,
        test_results=visible_results,
        passed_count=execution.passed_checks,
        total_count=execution.total_checks,
        accuracy=execution.evaluation_score,
    )


def _application_result(
    playable: PlayableChallenge,
    execution: ChallengeExecutionResult,
) -> ApplicationRunResult:
    changes = next(a for a in execution.artifacts if isinstance(a, ChangedFilesArtifact))
    build = next(a for a in execution.artifacts if isinstance(a, BuildArtifact))
    return ApplicationRunResult(
        challenge_id=playable.challenge.id,
        challenge_slug=playable.challenge.slug,
        challenge_version_id=playable.version.version_id,
        passed_count=execution.passed_checks,
        total_count=execution.total_checks,
        evaluation_score=execution.evaluation_score,
        checks=tuple(
            ApplicationCheckRunResult(
                check_id=result.test_case_id,
                label=result.label or "Application check",
                passed=result.grade.passed,
                message=result.grade.diagnostic.message if result.grade.diagnostic else None,
            )
            for result in execution.check_results
        ),
        changes=changes,
        build=build,
        screenshots=tuple(a for a in execution.artifacts if isinstance(a, ScreenshotArtifact)),
    )
