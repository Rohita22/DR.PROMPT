from dataclasses import dataclass
from enum import StrEnum

from app.domains.challenges.models import PlayableChallenge
from app.domains.progression.models import UserProgressItem


class ChallengeStatus(StrEnum):
    LOCKED = "locked"
    AVAILABLE = "available"
    COMPLETED = "completed"
    MASTERED = "mastered"


@dataclass(frozen=True, slots=True)
class ChallengeAccess:
    challenge: PlayableChallenge
    status: ChallengeStatus
    best_score: float | None
    best_stars: int
    attempts: int

    @property
    def completed(self) -> bool:
        return self.best_stars >= 1

    @property
    def accessible(self) -> bool:
        return self.status is not ChallengeStatus.LOCKED


class ChallengeProgressionService:
    """Derive linear track access from ordering and authoritative progress."""

    def evaluate_path(
        self,
        challenges: tuple[PlayableChallenge, ...],
        progress: tuple[UserProgressItem, ...] = (),
    ) -> tuple[ChallengeAccess, ...]:
        ordered = tuple(sorted(challenges, key=lambda item: item.challenge.order))
        progress_by_slug = {item.challenge_slug: item for item in progress}
        result: list[ChallengeAccess] = []
        previous_completed = True
        for index, playable in enumerate(ordered):
            item = progress_by_slug.get(playable.challenge.slug)
            best_stars = item.best_stars if item is not None else 0
            if best_stars >= 3:
                status = ChallengeStatus.MASTERED
            elif best_stars >= 1:
                status = ChallengeStatus.COMPLETED
            elif index == 0 or previous_completed:
                status = ChallengeStatus.AVAILABLE
            else:
                status = ChallengeStatus.LOCKED
            result.append(
                ChallengeAccess(
                    challenge=playable,
                    status=status,
                    best_score=item.best_score if item is not None else None,
                    best_stars=best_stars,
                    attempts=item.attempts if item is not None else 0,
                )
            )
            previous_completed = best_stars >= 1
        return tuple(result)
