import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError, PersistenceError
from app.domains.challenges.models import (
    ChallengeTrack,
    Difficulty,
    PlayableChallenge,
    PublicationState,
)
from app.domains.evaluation.test_cases import HiddenTestSuite
from app.domains.progression import (
    ProgressionResult,
    ProgressionService,
    UserChallengeProgress,
    UserProgressItem,
    UserProgressSummary,
    XPAwardReason,
    XPRewardConfiguration,
)
from app.domains.submissions.models import Submission
from app.infrastructure.database.mappers import hidden_suite_from_rows, playable_challenge_from_rows
from app.infrastructure.database.models import (
    ChallengeRow,
    ChallengeVersionRow,
    HiddenTestCaseRow,
    SubmissionRow,
    UserProgressRow,
    UserRow,
    VisibleExampleRow,
    VisibleTestCaseRow,
    XPTransactionRow,
)


class PostgresChallengeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_slug(self, slug: str) -> PlayableChallenge | None:
        try:
            async with self._session.begin():
                challenge = await self._session.scalar(
                    select(ChallengeRow).where(ChallengeRow.slug == slug)
                )
                return await self._load_playable(challenge)
        except (DomainError, SQLAlchemyError):
            raise PersistenceError("Database operation failed.") from None

    async def list_published(
        self,
        track: ChallengeTrack | None = None,
    ) -> tuple[PlayableChallenge, ...]:
        try:
            async with self._session.begin():
                query = select(ChallengeRow)
                if track is not None:
                    query = query.where(ChallengeRow.track == track.value)
                rows = (
                    await self._session.scalars(
                        query.order_by(ChallengeRow.track, ChallengeRow.sort_order)
                    )
                ).all()
                result: list[PlayableChallenge] = []
                for row in rows:
                    playable = await self._load_playable(row)
                    if playable is not None:
                        result.append(playable)
                return tuple(result)
        except (DomainError, SQLAlchemyError):
            raise PersistenceError("Database operation failed.") from None

    async def _load_playable(self, challenge: ChallengeRow | None) -> PlayableChallenge | None:
        if challenge is None or challenge.current_version is None:
            return None
        version = await self._session.scalar(
            select(ChallengeVersionRow).where(
                ChallengeVersionRow.challenge_id == challenge.id,
                ChallengeVersionRow.version == challenge.current_version,
                ChallengeVersionRow.publication_state == PublicationState.PUBLISHED.value,
            )
        )
        if version is None:
            return None
        examples = list(
            (
                await self._session.scalars(
                    select(VisibleExampleRow)
                    .where(VisibleExampleRow.challenge_version_id == version.id)
                    .order_by(VisibleExampleRow.sort_order)
                )
            ).all()
        )
        tests = list(
            (
                await self._session.scalars(
                    select(VisibleTestCaseRow)
                    .where(VisibleTestCaseRow.challenge_version_id == version.id)
                    .order_by(VisibleTestCaseRow.sort_order)
                )
            ).all()
        )
        return playable_challenge_from_rows(challenge, version, examples, tests)


class PostgresHiddenTestSuiteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_version(
        self,
        challenge_id: str,
        challenge_version_id: str,
    ) -> HiddenTestSuite | None:
        try:
            async with self._session.begin():
                version = await self._session.scalar(
                    select(ChallengeVersionRow).where(
                        ChallengeVersionRow.challenge_id == challenge_id,
                        ChallengeVersionRow.version == challenge_version_id,
                    )
                )
                if version is None:
                    return None
                tests = list(
                    (
                        await self._session.scalars(
                            select(HiddenTestCaseRow)
                            .where(HiddenTestCaseRow.challenge_version_id == version.id)
                            .order_by(HiddenTestCaseRow.sort_order)
                        )
                    ).all()
                )
                return hidden_suite_from_rows(version.version, tests)
        except (DomainError, SQLAlchemyError):
            raise PersistenceError("Database operation failed.") from None


class PostgresSubmissionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._progression = ProgressionService()

    async def save_with_progression(
        self,
        submission: Submission,
        *,
        difficulty: Difficulty,
        xp_configuration: XPRewardConfiguration,
    ) -> ProgressionResult:
        if submission.user_id is None:
            raise PersistenceError("Authoritative submission ownership is required.")
        try:
            async with self._session.begin():
                user_id = uuid.UUID(submission.user_id)
                owner = await self._session.scalar(
                    select(UserRow).where(UserRow.id == user_id).with_for_update()
                )
                if owner is None:
                    raise PersistenceError("Submission owner is unavailable.")
                version_id = await self._session.scalar(
                    select(ChallengeVersionRow.id).where(
                        ChallengeVersionRow.challenge_id == submission.challenge_id,
                        ChallengeVersionRow.version == submission.challenge_version_id,
                    )
                )
                if version_id is None:
                    raise PersistenceError("Submission challenge version is unavailable.")
                submission_row = SubmissionRow(
                    id=uuid.UUID(submission.id),
                    challenge_id=submission.challenge_id,
                    challenge_version_id=version_id,
                    user_id=user_id,
                    prompt=submission.prompt,
                    prompt_tokens=submission.prompt_tokens,
                    passed_tests=submission.passed_tests,
                    total_tests=submission.total_tests,
                    accuracy=submission.accuracy,
                    efficiency=submission.efficiency,
                    final_score=submission.final_score,
                    stars=submission.stars,
                    model_identifier=submission.model_identifier,
                    model_configuration_version=submission.model_configuration_version,
                    created_at=submission.created_at,
                )
                self._session.add(submission_row)
                await self._session.flush()

                progress_row = await self._session.scalar(
                    select(UserProgressRow)
                    .where(
                        UserProgressRow.user_id == user_id,
                        UserProgressRow.challenge_id == submission.challenge_id,
                    )
                    .with_for_update()
                )
                existing = _progress_from_row(progress_row) if progress_row is not None else None
                awarded_reasons = frozenset(
                    XPAwardReason(value)
                    for value in (
                        await self._session.scalars(
                            select(XPTransactionRow.reason).where(
                                XPTransactionRow.user_id == user_id,
                                XPTransactionRow.challenge_id == submission.challenge_id,
                            )
                        )
                    ).all()
                )
                progress = self._progression.update_progress(
                    submission=submission,
                    existing=existing,
                    occurred_at=submission.created_at,
                )
                awards = self._progression.new_awards(
                    stars=submission.stars,
                    difficulty=difficulty,
                    awarded_reasons=awarded_reasons,
                    configuration=xp_configuration,
                )
                if progress_row is None:
                    self._session.add(_progress_to_row(progress))
                else:
                    _update_progress_row(progress_row, progress)
                self._session.add_all(
                    XPTransactionRow(
                        id=uuid.uuid4(),
                        user_id=user_id,
                        challenge_id=submission.challenge_id,
                        submission_id=submission_row.id,
                        reason=award.reason.value,
                        amount=award.amount,
                        created_at=submission.created_at,
                    )
                    for award in awards
                )
                await self._session.flush()
                total_xp = int(
                    await self._session.scalar(
                        select(func.coalesce(func.sum(XPTransactionRow.amount), 0)).where(
                            XPTransactionRow.user_id == user_id
                        )
                    )
                    or 0
                )
                return ProgressionResult(progress, awards, total_xp)
        except PersistenceError:
            raise
        except (SQLAlchemyError, ValueError):
            raise PersistenceError("Database operation failed.") from None


class PostgresUserProgressRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_summary(self, user_id: str) -> UserProgressSummary:
        try:
            owner_id = uuid.UUID(user_id)
            async with self._session.begin():
                rows = (
                    await self._session.execute(
                        select(UserProgressRow, ChallengeRow.slug)
                        .join(ChallengeRow, ChallengeRow.id == UserProgressRow.challenge_id)
                        .where(UserProgressRow.user_id == owner_id)
                        .order_by(ChallengeRow.sort_order, ChallengeRow.slug)
                    )
                ).all()
                total_xp = int(
                    await self._session.scalar(
                        select(func.coalesce(func.sum(XPTransactionRow.amount), 0)).where(
                            XPTransactionRow.user_id == owner_id
                        )
                    )
                    or 0
                )
                challenges = tuple(
                    UserProgressItem(
                        challenge_slug=slug,
                        best_score=progress.best_score,
                        best_stars=progress.best_stars,
                        attempts=progress.attempts,
                        completed_at=progress.completed_at,
                    )
                    for progress, slug in rows
                )
                return UserProgressSummary(
                    total_xp=total_xp,
                    challenges_completed=sum(item.completed for item in challenges),
                    stars_earned=sum(item.best_stars for item in challenges),
                    challenges=challenges,
                )
        except (SQLAlchemyError, ValueError):
            raise PersistenceError("Database operation failed.") from None


def _progress_from_row(row: UserProgressRow) -> UserChallengeProgress:
    return UserChallengeProgress(
        id=str(row.id),
        user_id=str(row.user_id),
        challenge_id=row.challenge_id,
        best_submission_id=str(row.best_submission_id),
        best_score=row.best_score,
        best_stars=row.best_stars,
        attempts=row.attempts,
        completed_at=row.completed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _progress_to_row(progress: UserChallengeProgress) -> UserProgressRow:
    return UserProgressRow(
        id=uuid.UUID(progress.id),
        user_id=uuid.UUID(progress.user_id),
        challenge_id=progress.challenge_id,
        best_submission_id=uuid.UUID(progress.best_submission_id),
        best_score=progress.best_score,
        best_stars=progress.best_stars,
        attempts=progress.attempts,
        completed_at=progress.completed_at,
        created_at=progress.created_at,
        updated_at=progress.updated_at,
    )


def _update_progress_row(
    row: UserProgressRow,
    progress: UserChallengeProgress,
) -> None:
    row.best_submission_id = uuid.UUID(progress.best_submission_id)
    row.best_score = progress.best_score
    row.best_stars = progress.best_stars
    row.attempts = progress.attempts
    row.completed_at = progress.completed_at
    row.updated_at = progress.updated_at
