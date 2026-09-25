from datetime import datetime
from uuid import uuid4

from app.domains.challenges.models import Difficulty
from app.domains.progression.models import (
    UserChallengeProgress,
    XPAward,
    XPAwardReason,
    XPRewardConfiguration,
)
from app.domains.submissions.models import Submission


class ProgressionService:
    """Pure progression policy for one completed authoritative evaluation."""

    def update_progress(
        self,
        *,
        submission: Submission,
        existing: UserChallengeProgress | None,
        occurred_at: datetime,
    ) -> UserChallengeProgress:
        if existing is None:
            return UserChallengeProgress(
                id=str(uuid4()),
                user_id=self._owner_id(submission),
                challenge_id=submission.challenge_id,
                best_submission_id=submission.id,
                best_score=submission.final_score,
                best_stars=submission.stars,
                attempts=1,
                completed_at=occurred_at if submission.stars >= 1 else None,
                created_at=occurred_at,
                updated_at=occurred_at,
            )

        better_score = submission.final_score > existing.best_score
        return UserChallengeProgress(
            id=existing.id,
            user_id=existing.user_id,
            challenge_id=existing.challenge_id,
            best_submission_id=(submission.id if better_score else existing.best_submission_id),
            best_score=max(existing.best_score, submission.final_score),
            best_stars=max(existing.best_stars, submission.stars),
            attempts=existing.attempts + 1,
            completed_at=(
                existing.completed_at
                if existing.completed_at is not None
                else occurred_at
                if submission.stars >= 1
                else None
            ),
            created_at=existing.created_at,
            updated_at=occurred_at,
        )

    def new_awards(
        self,
        *,
        stars: int,
        difficulty: Difficulty,
        awarded_reasons: frozenset[XPAwardReason],
        configuration: XPRewardConfiguration,
    ) -> tuple[XPAward, ...]:
        if stars < 1:
            return ()

        candidates: list[XPAward] = []

        def add(reason: XPAwardReason, amount: int) -> None:
            if amount > 0:
                candidates.append(XPAward(reason, amount))

        if difficulty is Difficulty.BOSS:
            add(XPAwardReason.BOSS_COMPLETION, configuration.boss_completion)
            if not configuration.boss_replaces_first_completion:
                add(XPAwardReason.FIRST_COMPLETION, configuration.first_completion)
        else:
            add(XPAwardReason.FIRST_COMPLETION, configuration.first_completion)
        if stars >= 2:
            add(XPAwardReason.TWO_STAR, configuration.two_star)
        if stars >= 3:
            add(XPAwardReason.THREE_STAR, configuration.three_star)
        return tuple(award for award in candidates if award.reason not in awarded_reasons)

    @staticmethod
    def _owner_id(submission: Submission) -> str:
        if submission.user_id is None:
            raise ValueError("Progression requires an owned submission.")
        return submission.user_id
