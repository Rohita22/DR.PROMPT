from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class LeaderboardEntryResult:
    rank: int
    player: str
    score: float
    accuracy: float
    prompt_tokens: int
    stars: int
    submitted_at: datetime
    is_current_user: bool


@dataclass(frozen=True, slots=True)
class ChallengeLeaderboardResult:
    challenge_slug: str
    challenge_version_id: str
    entries: tuple[LeaderboardEntryResult, ...]
    current_user_entry: LeaderboardEntryResult | None
    total_entries: int
    limit: int
    offset: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.entries) < self.total_entries
