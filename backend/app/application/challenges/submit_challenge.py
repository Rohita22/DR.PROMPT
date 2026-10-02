from datetime import UTC, datetime
from uuid import uuid4

from app.application.challenges.access import ChallengeAccessService
from app.application.challenges.errors import PromptTooLongError
from app.application.challenges.execution_guard import (
    ApplicationExecutionScope,
    ApplicationExecutionService,
    ApplicationSubmissionRepository,
)
from app.application.challenges.models import (
    ApplicationSubmitResult,
    SubmitChallengeCommand,
    SubmitChallengeResult,
)
from app.domains.challenges.errors import ChallengeNotFoundError
from app.domains.challenges.models import ChallengeType, PlayableChallenge
from app.domains.challenges.ports import ChallengeReader
from app.domains.execution import (
    ChallengeExecutionRequest,
    ChallengeExecutorResolver,
    ChangedFilesArtifact,
    ScreenshotArtifact,
)
from app.domains.progression import XPRewardConfiguration
from app.domains.scoring.ports import PromptTokenCounter
from app.domains.scoring.service import ScoringService
from app.domains.submissions import Submission, SubmissionRepository


class SubmitChallengeUseCase:
    """Execute hidden tests and expose only aggregate evaluation information."""

    def __init__(
        self,
        challenge_reader: ChallengeReader,
        executor_resolver: ChallengeExecutorResolver,
        prompt_token_counter: PromptTokenCounter,
        scoring_service: ScoringService,
        submission_repository: SubmissionRepository,
        access_service: ChallengeAccessService,
        xp_configuration: XPRewardConfiguration | None = None,
        application_execution_service: ApplicationExecutionService | None = None,
        application_submission_repository: ApplicationSubmissionRepository | None = None,
    ) -> None:
        self._challenge_reader = challenge_reader
        self._executor_resolver = executor_resolver
        self._prompt_token_counter = prompt_token_counter
        self._scoring_service = scoring_service
        self._submission_repository = submission_repository
        self._access_service = access_service
        self._xp_configuration = xp_configuration or XPRewardConfiguration()
        self._application_execution_service = application_execution_service
        self._application_submission_repository = application_submission_repository

    async def execute(
        self,
        command: SubmitChallengeCommand,
    ) -> SubmitChallengeResult | ApplicationSubmitResult:
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

        if (
            version.challenge_type is ChallengeType.APPLICATION
            and self._application_execution_service
        ):
            scope = ApplicationExecutionScope(
                user_id=command.owner_user_id,
                challenge_id=playable.challenge.id,
                challenge_slug=playable.challenge.slug,
                challenge_version_id=version.version_id,
            )
            async with self._application_execution_service.submit(
                scope, command.idempotency_key
            ) as start:
                if start.replay is not None:
                    return start.replay
                return await self._execute_and_persist_application(
                    playable, command, prompt_tokens, start.reservation_id
                )

        executor = self._executor_resolver.resolve(version.challenge_type)
        execution = await executor.execute_hidden(
            ChallengeExecutionRequest(playable=playable, player_prompt=command.player_prompt)
        )
        # Only aggregates leave this point; per-check hidden detail stays internal.
        # For APPLICATION the normalized evaluation score takes accuracy's scoring role.
        scoring = self._scoring_service.calculate(
            prompt_tokens=prompt_tokens,
            accuracy=execution.evaluation_score,
            configuration=version.scoring_config,
        )
        submission = Submission(
            id=str(uuid4()),
            challenge_id=playable.challenge.id,
            challenge_version_id=version.version_id,
            user_id=command.owner_user_id,
            prompt=command.player_prompt,
            prompt_tokens=scoring.prompt_tokens,
            passed_tests=execution.passed_checks,
            total_tests=execution.total_checks,
            accuracy=execution.evaluation_score,
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
        completed = progression.progress.completed_at is not None
        if version.challenge_type is ChallengeType.APPLICATION:
            changes = next(a for a in execution.artifacts if isinstance(a, ChangedFilesArtifact))
            # The player's own desktop result is safe to show; hidden viewports are not.
            screenshot = next(
                (a for a in execution.artifacts if isinstance(a, ScreenshotArtifact)),
                None,
            )
            return ApplicationSubmitResult(
                challenge_slug=playable.challenge.slug,
                challenge_version_id=version.version_id,
                passed_count=execution.passed_checks,
                total_count=execution.total_checks,
                evaluation_score=execution.evaluation_score,
                prompt_tokens=scoring.prompt_tokens,
                efficiency=scoring.efficiency,
                final_score=scoring.final_score,
                stars=scoring.stars,
                xp_earned=progression.xp_earned,
                total_xp=progression.total_xp,
                best_score=progression.progress.best_score,
                best_stars=progression.progress.best_stars,
                completed=completed,
                agent_status=changes.agent_status,
                screenshot=screenshot,
            )
        return SubmitChallengeResult(
            challenge_slug=playable.challenge.slug,
            challenge_version_id=version.version_id,
            passed_count=execution.passed_checks,
            total_count=execution.total_checks,
            accuracy=execution.evaluation_score,
            prompt_tokens=scoring.prompt_tokens,
            efficiency=scoring.efficiency,
            final_score=scoring.final_score,
            stars=scoring.stars,
            xp_earned=progression.xp_earned,
            total_xp=progression.total_xp,
            best_score=progression.progress.best_score,
            best_stars=progression.progress.best_stars,
            completed=completed,
        )

    async def _execute_and_persist_application(
        self,
        playable: PlayableChallenge,
        command: SubmitChallengeCommand,
        prompt_tokens: int,
        reservation_id: str | None,
    ) -> ApplicationSubmitResult:
        if reservation_id is None or self._application_submission_repository is None:
            raise RuntimeError("APPLICATION Submit persistence is not configured.")
        version = playable.version
        executor = self._executor_resolver.resolve(ChallengeType.APPLICATION)
        execution = await executor.execute_hidden(
            ChallengeExecutionRequest(playable=playable, player_prompt=command.player_prompt)
        )
        scoring = self._scoring_service.calculate(
            prompt_tokens=prompt_tokens,
            accuracy=execution.evaluation_score,
            configuration=version.scoring_config,
        )
        submission = Submission(
            id=str(uuid4()),
            challenge_id=playable.challenge.id,
            challenge_version_id=version.version_id,
            user_id=command.owner_user_id,
            prompt=command.player_prompt,
            prompt_tokens=scoring.prompt_tokens,
            passed_tests=execution.passed_checks,
            total_tests=execution.total_checks,
            accuracy=execution.evaluation_score,
            efficiency=scoring.efficiency,
            final_score=scoring.final_score,
            stars=scoring.stars,
            model_identifier=version.model_config.model_id,
            model_configuration_version=version.model_config.configuration_version,
            created_at=datetime.now(UTC),
        )
        changes = next(a for a in execution.artifacts if isinstance(a, ChangedFilesArtifact))
        screenshot = next(
            (a for a in execution.artifacts if isinstance(a, ScreenshotArtifact)),
            None,
        )
        provisional = ApplicationSubmitResult(
            challenge_slug=playable.challenge.slug,
            challenge_version_id=version.version_id,
            passed_count=execution.passed_checks,
            total_count=execution.total_checks,
            evaluation_score=execution.evaluation_score,
            prompt_tokens=scoring.prompt_tokens,
            efficiency=scoring.efficiency,
            final_score=scoring.final_score,
            stars=scoring.stars,
            xp_earned=0,
            total_xp=0,
            best_score=0,
            best_stars=0,
            completed=False,
            agent_status=changes.agent_status,
            screenshot=screenshot,
        )
        return await self._application_submission_repository.save_application_with_progression(
            submission,
            difficulty=version.difficulty,
            xp_configuration=self._xp_configuration,
            reservation_id=reservation_id,
            result=provisional,
        )
