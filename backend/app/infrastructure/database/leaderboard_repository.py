import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError, PersistenceError
from app.domains.leaderboard import LeaderboardPage, RankedLeaderboardSubmission
from app.infrastructure.database.models import ChallengeVersionRow, SubmissionRow, UserRow


class PostgresLeaderboardRepository:
    """Ranks one comparable best submission per user with PostgreSQL windows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_page(
        self,
        *,
        challenge_id: str,
        challenge_version_id: str,
        model_identifier: str,
        model_configuration_version: str,
        limit: int,
        offset: int,
        current_user_id: str | None,
    ) -> LeaderboardPage:
        try:
            async with self._session.begin():
                version_database_id = await self._session.scalar(
                    select(ChallengeVersionRow.id).where(
                        ChallengeVersionRow.challenge_id == challenge_id,
                        ChallengeVersionRow.version == challenge_version_id,
                    )
                )
                if version_database_id is None:
                    return LeaderboardPage((), 0, None)

                product_order = (
                    SubmissionRow.final_score.desc(),
                    SubmissionRow.accuracy.desc(),
                    SubmissionRow.prompt_tokens.asc(),
                    SubmissionRow.created_at.asc(),
                    SubmissionRow.id.asc(),
                )
                eligible = (
                    select(
                        SubmissionRow.id.label("submission_id"),
                        SubmissionRow.user_id.label("user_id"),
                        SubmissionRow.final_score.label("score"),
                        SubmissionRow.accuracy.label("accuracy"),
                        SubmissionRow.prompt_tokens.label("prompt_tokens"),
                        SubmissionRow.stars.label("stars"),
                        SubmissionRow.created_at.label("submitted_at"),
                        func.row_number()
                        .over(partition_by=SubmissionRow.user_id, order_by=product_order)
                        .label("user_position"),
                    )
                    .where(
                        SubmissionRow.challenge_id == challenge_id,
                        SubmissionRow.challenge_version_id == version_database_id,
                        SubmissionRow.model_identifier == model_identifier,
                        SubmissionRow.model_configuration_version == model_configuration_version,
                        SubmissionRow.user_id.is_not(None),
                    )
                    .cte("eligible_submissions")
                )
                user_best = (
                    select(
                        eligible.c.submission_id,
                        eligible.c.user_id,
                        eligible.c.score,
                        eligible.c.accuracy,
                        eligible.c.prompt_tokens,
                        eligible.c.stars,
                        eligible.c.submitted_at,
                    )
                    .where(eligible.c.user_position == 1)
                    .cte("user_best_submissions")
                )
                global_order = (
                    user_best.c.score.desc(),
                    user_best.c.accuracy.desc(),
                    user_best.c.prompt_tokens.asc(),
                    user_best.c.submitted_at.asc(),
                    user_best.c.submission_id.asc(),
                )
                ranked = select(
                    user_best,
                    func.row_number().over(order_by=global_order).label("rank"),
                ).cte("ranked_submissions")
                base_query = select(
                    ranked.c.rank,
                    ranked.c.submission_id,
                    ranked.c.user_id,
                    UserRow.username,
                    ranked.c.score,
                    ranked.c.accuracy,
                    ranked.c.prompt_tokens,
                    ranked.c.stars,
                    ranked.c.submitted_at,
                ).join(UserRow, UserRow.id == ranked.c.user_id)
                rows = (
                    await self._session.execute(
                        base_query.where(
                            ranked.c.rank > offset, ranked.c.rank <= offset + limit
                        ).order_by(ranked.c.rank)
                    )
                ).all()
                total_entries = int(
                    await self._session.scalar(select(func.count()).select_from(ranked)) or 0
                )
                current_row = None
                if current_user_id is not None:
                    current_row = (
                        await self._session.execute(
                            base_query.where(ranked.c.user_id == uuid.UUID(current_user_id))
                        )
                    ).one_or_none()

                return LeaderboardPage(
                    entries=tuple(_entry_from_row(row) for row in rows),
                    total_entries=total_entries,
                    current_user_entry=(
                        _entry_from_row(current_row) if current_row is not None else None
                    ),
                )
        except (DomainError, SQLAlchemyError, ValueError):
            raise PersistenceError("Database operation failed.") from None


def _entry_from_row(row: object) -> RankedLeaderboardSubmission:
    mapping = row._mapping  # type: ignore[attr-defined]
    return RankedLeaderboardSubmission(
        rank=int(mapping["rank"]),
        submission_id=str(mapping["submission_id"]),
        user_id=str(mapping["user_id"]),
        username=mapping["username"],
        score=float(mapping["score"]),
        accuracy=float(mapping["accuracy"]),
        prompt_tokens=int(mapping["prompt_tokens"]),
        stars=int(mapping["stars"]),
        submitted_at=mapping["submitted_at"],
    )
