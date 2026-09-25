from datetime import UTC, datetime
from uuid import uuid4

from app.application.challenges.access import ChallengeAccessService
from app.application.challenges.errors import PromptTooLongError
from app.application.challenges.models import (
    SubmitChallengeCommand,
    SubmitChallengeResult,
)
from app.domains.challenges.errors import ChallengeNotFoundError
from app.domains.challenges.ports import ChallengeReader
from app.domains.evaluation.engine import EvaluationEngine
from app.domains.evaluation.errors import (
    HiddenTestSuiteNotFoundError,
    HiddenTestSuiteVersionMismatchError,
)
from app.domains.evaluation.model_execution import LLMExecutionRequest
from app.domains.evaluation.ports import HiddenTestSuiteReader, LLMProvider
from app.domains.progression import XPRewardConfiguration
from app.domains.scoring.ports import PromptTokenCounter
from app.domains.scoring.service import ScoringService
from app.domains.submissions import Submission, SubmissionRepository


class SubmitChallengeUseCase:
    """Execute hidden tests and expose only aggregate evaluation information."""

    def __init__(
        self,
        challenge_reader: ChallengeReader,
        hidden_test_suite_reader: HiddenTestSuiteReader,
        llm_provider: LLMProvider,
        evaluation_engine: EvaluationEngine,
        prompt_token_counter: PromptTokenCounter,
        scoring_service: ScoringService,
        submission_repository: SubmissionRepository,
        access_service: ChallengeAccessService,
        xp_configuration: XPRewardConfiguration | None = None,
    ) -> None:
        self._challenge_reader = challenge_reader
        self._hidden_test_suite_reader = hidden_test_suite_reader
        self._llm_provider = llm_provider
        self._evaluation_engine = evaluation_engine
        self._prompt_token_counter = prompt_token_counter
        self._scoring_service = scoring_service
        self._submission_repository = submission_repository
        self._access_service = access_service
        self._xp_configuration = xp_configuration or XPRewardConfiguration()

    async def execute(self, command: SubmitChallengeCommand) -> SubmitChallengeResult:
        playable = await self._challenge_reader.get_by_slug(command.challenge_slug)
        if playable is None:
            raise ChallengeNotFoundError(
                f"Published challenge '{command.challenge_slug}' was not found."
            )

        await self._access_service.require_access(playable, command.owner_user_id)

        version = playable.version
        prompt_tokens = self._prompt_token_counter.count(
            command.player_prompt,
            version.model_config.model_id,
        )
        if version.prompt_token_limit is not None and prompt_tokens > version.prompt_token_limit:
            raise PromptTooLongError(
                actual_tokens=prompt_tokens,
                maximum_tokens=version.prompt_token_limit,
            )

        suite = await self._hidden_test_suite_reader.get_for_version(
            playable.challenge.id,
            version.version_id,
        )
        if suite is None:
            raise HiddenTestSuiteNotFoundError("Challenge evaluation is unavailable.")
        if suite.challenge_version_id != version.version_id:
            raise HiddenTestSuiteVersionMismatchError("Challenge evaluation is unavailable.")

        outputs = {}
        for test_case in suite.test_cases:
            execution = await self._llm_provider.generate(
                LLMExecutionRequest(
                    player_prompt=command.player_prompt,
                    test_input=test_case.input,
                    model_config=version.model_config,
                )
            )
            outputs[test_case.id] = execution.output_text

        evaluation = self._evaluation_engine.evaluate_batch(suite.test_cases, outputs)
        scoring = self._scoring_service.calculate(
            prompt_tokens=prompt_tokens,
            accuracy=evaluation.accuracy,
            configuration=version.scoring_config,
        )
        submission = Submission(
            id=str(uuid4()),
            challenge_id=playable.challenge.id,
            challenge_version_id=version.version_id,
            user_id=command.owner_user_id,
            prompt=command.player_prompt,
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
        progression = await self._submission_repository.save_with_progression(
            submission,
            difficulty=version.difficulty,
            xp_configuration=self._xp_configuration,
        )
        return SubmitChallengeResult(
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
