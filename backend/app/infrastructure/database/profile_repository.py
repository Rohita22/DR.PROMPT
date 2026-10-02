import uuid

from sqlalchemy import and_, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError, PersistenceError
from app.domains.challenges.models import PublicationState
from app.domains.profile import ProfileActivity, ProfileSnapshot
from app.infrastructure.database.models import (
    ChallengeRow,
    ChallengeVersionRow,
    SubmissionRow,
    UserProgressRow,
    XPTransactionRow,
)


class PostgresProfileRepository:
    """Build a current-player read model without persisting duplicated aggregates."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_snapshot(self, user_id: str, *, recent_limit: int) -> ProfileSnapshot:
        try:
            owner_id = uuid.UUID(user_id)
            async with self._session.begin():
                published = (
                    select(ChallengeRow.id.label("challenge_id"))
                    .join(
                        ChallengeVersionRow,
                        and_(
                            ChallengeVersionRow.challenge_id == ChallengeRow.id,
                            ChallengeVersionRow.version == ChallengeRow.current_version,
                            ChallengeVersionRow.publication_state
                            == PublicationState.PUBLISHED.value,
                        ),
                    )
                    .cte("published_profile_challenges")
                )
                published_count = int(
                    await self._session.scalar(select(func.count()).select_from(published)) or 0
                )
                progress_row = (
                    await self._session.execute(
                        select(
                            func.count().filter(UserProgressRow.best_stars >= 1).label("completed"),
                            func.coalesce(func.sum(UserProgressRow.best_stars), 0).label("stars"),
                            func.count()
                            .filter(UserProgressRow.best_stars == 3)
                            .label("perfect_clears"),
                        ).where(
                            UserProgressRow.user_id == owner_id,
                            UserProgressRow.challenge_id.in_(select(published.c.challenge_id)),
                        )
                    )
                ).one()
                total_xp = int(
                    await self._session.scalar(
                        select(func.coalesce(func.sum(XPTransactionRow.amount), 0)).where(
                            XPTransactionRow.user_id == owner_id
                        )
                    )
                    or 0
                )
                best_rank = await self._best_leaderboard_rank(owner_id)
                activity = await self._recent_activity(owner_id, recent_limit)
                return ProfileSnapshot(
                    total_xp=total_xp,
                    published_challenges=published_count,
                    challenges_completed=int(progress_row.completed),
                    stars_earned=int(progress_row.stars),
                    three_star_completions=int(progress_row.perfect_clears),
                    best_leaderboard_rank=best_rank,
                    recent_activity=activity,
                )
        except (DomainError, SQLAlchemyError, ValueError):
            raise PersistenceError("Database operation failed.") from None

    async def _best_leaderboard_rank(self, owner_id: uuid.UUID) -> int | None:
        product_order = (
            SubmissionRow.final_score.desc(),
            SubmissionRow.accuracy.desc(),
            SubmissionRow.prompt_tokens.asc(),
            SubmissionRow.created_at.asc(),
            SubmissionRow.id.asc(),
        )
        eligible = (
            select(
                SubmissionRow.challenge_id.label("challenge_id"),
                SubmissionRow.id.label("submission_id"),
                SubmissionRow.user_id.label("user_id"),
                SubmissionRow.final_score.label("score"),
                SubmissionRow.accuracy.label("accuracy"),
                SubmissionRow.prompt_tokens.label("prompt_tokens"),
                SubmissionRow.created_at.label("submitted_at"),
                func.row_number()
                .over(
                    partition_by=(SubmissionRow.challenge_id, SubmissionRow.user_id),
                    order_by=product_order,
                )
                .label("user_position"),
            )
            .join(ChallengeRow, ChallengeRow.id == SubmissionRow.challenge_id)
            .join(
                ChallengeVersionRow,
                and_(
                    ChallengeVersionRow.id == SubmissionRow.challenge_version_id,
                    ChallengeVersionRow.challenge_id == ChallengeRow.id,
                    ChallengeVersionRow.version == ChallengeRow.current_version,
                    ChallengeVersionRow.publication_state == PublicationState.PUBLISHED.value,
                ),
            )
            .where(
                SubmissionRow.user_id.is_not(None),
                SubmissionRow.model_identifier
                == ChallengeVersionRow.model_config["model_id"].as_string(),
                SubmissionRow.model_configuration_version
                == ChallengeVersionRow.model_config["configuration_version"].as_string(),
            )
            .cte("profile_eligible_submissions")
        )
        user_best = (
            select(
                eligible.c.challenge_id,
                eligible.c.submission_id,
                eligible.c.user_id,
                eligible.c.score,
                eligible.c.accuracy,
                eligible.c.prompt_tokens,
                eligible.c.submitted_at,
            )
            .where(eligible.c.user_position == 1)
            .cte("profile_user_best_submissions")
        )
        global_order = (
            user_best.c.score.desc(),
            user_best.c.accuracy.desc(),
            user_best.c.prompt_tokens.asc(),
            user_best.c.submitted_at.asc(),
            user_best.c.submission_id.asc(),
        )
        ranked = select(
            user_best.c.user_id,
            func.row_number()
            .over(partition_by=user_best.c.challenge_id, order_by=global_order)
            .label("rank"),
        ).cte("profile_ranked_submissions")
        rank = await self._session.scalar(
            select(func.min(ranked.c.rank)).where(ranked.c.user_id == owner_id)
        )
        return int(rank) if rank is not None else None

    async def _recent_activity(
        self,
        owner_id: uuid.UUID,
        limit: int,
    ) -> tuple[ProfileActivity, ...]:
        xp_by_submission = (
            select(
                XPTransactionRow.submission_id.label("submission_id"),
                func.sum(XPTransactionRow.amount).label("xp_earned"),
            )
            .where(XPTransactionRow.user_id == owner_id)
            .group_by(XPTransactionRow.submission_id)
            .cte("profile_xp_by_submission")
        )
        rows = (
            await self._session.execute(
                select(
                    ChallengeRow.slug.label("challenge_slug"),
                    ChallengeVersionRow.title.label("challenge_title"),
                    SubmissionRow.final_score.label("score"),
                    SubmissionRow.accuracy.label("accuracy"),
                    SubmissionRow.stars.label("stars"),
                    SubmissionRow.prompt_tokens.label("prompt_tokens"),
                    func.coalesce(xp_by_submission.c.xp_earned, 0).label("xp_earned"),
                    SubmissionRow.created_at.label("submitted_at"),
                )
                .join(ChallengeRow, ChallengeRow.id == SubmissionRow.challenge_id)
                .join(
                    ChallengeVersionRow,
                    ChallengeVersionRow.id == SubmissionRow.challenge_version_id,
                )
                .outerjoin(
                    xp_by_submission,
                    xp_by_submission.c.submission_id == SubmissionRow.id,
                )
                .where(SubmissionRow.user_id == owner_id)
                .order_by(SubmissionRow.created_at.desc(), SubmissionRow.id.desc())
                .limit(limit)
            )
        ).all()
        return tuple(
            ProfileActivity(
                challenge_slug=row.challenge_slug,
                challenge_title=row.challenge_title,
                score=float(row.score),
                accuracy=float(row.accuracy),
                stars=int(row.stars),
                prompt_tokens=int(row.prompt_tokens),
                xp_earned=int(row.xp_earned),
                submitted_at=row.submitted_at,
            )
            for row in rows
        )
