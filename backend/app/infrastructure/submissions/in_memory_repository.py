import asyncio
from uuid import uuid4

from app.domains.challenges.models import Difficulty
from app.domains.progression import (
    ProgressionResult,
    ProgressionService,
    UserChallengeProgress,
    UserProgressItem,
    UserProgressSummary,
    XPAwardReason,
    XPRewardConfiguration,
    XPTransaction,
)
from app.domains.submissions.models import Submission


class InMemorySubmissionRepository:
    def __init__(self, challenge_slugs: dict[str, str] | None = None) -> None:
        self.submissions: list[Submission] = []
        self.progress: dict[tuple[str, str], UserChallengeProgress] = {}
        self.xp_transactions: list[XPTransaction] = []
        self._lock = asyncio.Lock()
        self._progression = ProgressionService()
        self._challenge_slugs = challenge_slugs or {
            "control-exact-output": "exact-output",
            "control-output-restrictions": "output-restrictions",
            "control-formatting-rules": "formatting-rules",
            "control-multiple-constraints": "multiple-constraints",
            "control-control-boss": "control-boss",
        }

    async def save_with_progression(
        self,
        submission: Submission,
        *,
        difficulty: Difficulty,
        xp_configuration: XPRewardConfiguration,
    ) -> ProgressionResult:
        if submission.user_id is None:
            raise ValueError("Authoritative submissions require an owner.")
        async with self._lock:
            key = (submission.user_id, submission.challenge_id)
            existing = self.progress.get(key)
            awarded = frozenset(
                transaction.reason
                for transaction in self.xp_transactions
                if transaction.user_id == submission.user_id
                and transaction.challenge_id == submission.challenge_id
            )
            progress = self._progression.update_progress(
                submission=submission,
                existing=existing,
                occurred_at=submission.created_at,
            )
            awards = self._progression.new_awards(
                stars=submission.stars,
                difficulty=difficulty,
                awarded_reasons=awarded,
                configuration=xp_configuration,
            )
            self.submissions.append(submission)
            self.progress[key] = progress
            self.xp_transactions.extend(
                XPTransaction(
                    id=str(uuid4()),
                    user_id=submission.user_id,
                    challenge_id=submission.challenge_id,
                    submission_id=submission.id,
                    reason=award.reason,
                    amount=award.amount,
                    created_at=submission.created_at,
                )
                for award in awards
            )
            total_xp = sum(
                transaction.amount
                for transaction in self.xp_transactions
                if transaction.user_id == submission.user_id
            )
            return ProgressionResult(progress, awards, total_xp)

    def awarded_reasons(self, user_id: str, challenge_id: str) -> set[XPAwardReason]:
        return {
            transaction.reason
            for transaction in self.xp_transactions
            if transaction.user_id == user_id and transaction.challenge_id == challenge_id
        }

    async def get_summary(self, user_id: str) -> UserProgressSummary:
        challenges = tuple(
            UserProgressItem(
                challenge_slug=self._challenge_slugs.get(
                    progress.challenge_id,
                    progress.challenge_id,
                ),
                best_score=progress.best_score,
                best_stars=progress.best_stars,
                attempts=progress.attempts,
                completed_at=progress.completed_at,
            )
            for (owner_id, _challenge_id), progress in sorted(self.progress.items())
            if owner_id == user_id
        )
        return UserProgressSummary(
            total_xp=sum(
                transaction.amount
                for transaction in self.xp_transactions
                if transaction.user_id == user_id
            ),
            challenges_completed=sum(item.completed for item in challenges),
            stars_earned=sum(item.best_stars for item in challenges),
            challenges=challenges,
        )
