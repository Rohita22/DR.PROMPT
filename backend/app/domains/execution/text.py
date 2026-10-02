from collections.abc import Sequence

from app.domains.challenges.models import ChallengeType
from app.domains.evaluation.engine import EvaluationEngine, ExecutableTestCase
from app.domains.evaluation.errors import (
    HiddenTestSuiteNotFoundError,
    HiddenTestSuiteVersionMismatchError,
)
from app.domains.evaluation.model_execution import LLMExecutionRequest
from app.domains.evaluation.ports import HiddenTestSuiteReader, LLMProvider
from app.domains.execution.errors import UnsupportedChallengeTypeError
from app.domains.execution.models import (
    ChallengeExecutionRequest,
    ChallengeExecutionResult,
    TextOutputArtifact,
)


class TextChallengeExecutor:
    """TEXT family: one model call per test case, then deterministic grading."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        evaluation_engine: EvaluationEngine,
        hidden_test_suite_reader: HiddenTestSuiteReader,
    ) -> None:
        self._llm_provider = llm_provider
        self._evaluation_engine = evaluation_engine
        self._hidden_test_suite_reader = hidden_test_suite_reader

    async def execute_visible(
        self,
        request: ChallengeExecutionRequest,
    ) -> ChallengeExecutionResult:
        return await self._execute(request, request.playable.version.visible_test_cases)

    async def execute_hidden(
        self,
        request: ChallengeExecutionRequest,
    ) -> ChallengeExecutionResult:
        playable = request.playable
        suite = await self._hidden_test_suite_reader.get_for_version(
            playable.challenge.id,
            playable.version.version_id,
        )
        if suite is None:
            raise HiddenTestSuiteNotFoundError("Challenge evaluation is unavailable.")
        if suite.challenge_version_id != playable.version.version_id:
            raise HiddenTestSuiteVersionMismatchError("Challenge evaluation is unavailable.")
        return await self._execute(request, suite.test_cases)

    async def _execute(
        self,
        request: ChallengeExecutionRequest,
        test_cases: Sequence[ExecutableTestCase],
    ) -> ChallengeExecutionResult:
        version = request.playable.version
        if version.challenge_type is not ChallengeType.TEXT:
            raise UnsupportedChallengeTypeError(str(version.challenge_type))

        # Sequential and fail-fast: a provider error is an infrastructure failure,
        # never a wrong answer, so nothing is graded unless every call succeeds.
        outputs: dict[str, str] = {}
        for test_case in test_cases:
            execution = await self._llm_provider.generate(
                LLMExecutionRequest(
                    player_prompt=request.player_prompt,
                    test_input=test_case.input,
                    model_config=version.model_config,
                )
            )
            outputs[test_case.id] = execution.output_text

        evaluation = self._evaluation_engine.evaluate_batch(test_cases, outputs)
        return ChallengeExecutionResult(
            evaluation_score=evaluation.accuracy,
            passed_checks=evaluation.passed_count,
            total_checks=evaluation.total_count,
            check_results=evaluation.test_results,
            artifacts=tuple(
                TextOutputArtifact(test_case_id=test_id, output_text=output)
                for test_id, output in outputs.items()
            ),
        )
