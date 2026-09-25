from app.application.challenges.access import ChallengeAccessService
from app.application.challenges.models import (
    RunChallengeCommand,
    RunChallengeResult,
    VisibleTestRunResult,
)
from app.domains.challenges.errors import ChallengeNotFoundError
from app.domains.challenges.ports import ChallengeReader
from app.domains.evaluation.engine import EvaluationEngine
from app.domains.evaluation.model_execution import LLMExecutionRequest
from app.domains.evaluation.ports import LLMProvider


class RunChallengeUseCase:
    """Execute and grade every visible test for one playable challenge."""

    def __init__(
        self,
        challenge_reader: ChallengeReader,
        llm_provider: LLMProvider,
        evaluation_engine: EvaluationEngine,
        access_service: ChallengeAccessService,
    ) -> None:
        self._challenge_reader = challenge_reader
        self._llm_provider = llm_provider
        self._evaluation_engine = evaluation_engine
        self._access_service = access_service

    async def execute(self, command: RunChallengeCommand) -> RunChallengeResult:
        playable = await self._challenge_reader.get_by_slug(command.challenge_slug)
        if playable is None:
            raise ChallengeNotFoundError(
                f"Published challenge '{command.challenge_slug}' was not found."
            )
        await self._access_service.require_access(playable, command.owner_user_id)

        version = playable.version
        outputs = {}
        for test_case in version.visible_test_cases:
            execution = await self._llm_provider.generate(
                LLMExecutionRequest(
                    player_prompt=command.player_prompt,
                    test_input=test_case.input,
                    model_config=version.model_config,
                )
            )
            outputs[test_case.id] = execution.output_text

        evaluation = self._evaluation_engine.evaluate_batch(
            version.visible_test_cases,
            outputs,
        )
        grades_by_id = {result.test_case_id: result.grade for result in evaluation.test_results}
        visible_results = tuple(
            VisibleTestRunResult(
                test_id=test_case.id,
                input=test_case.input,
                expected_output=test_case.expected_output,
                actual_output=outputs[test_case.id],
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
            passed_count=evaluation.passed_count,
            total_count=evaluation.total_count,
            accuracy=evaluation.accuracy,
        )
