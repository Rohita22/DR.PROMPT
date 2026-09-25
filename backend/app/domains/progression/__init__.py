"""Server-authoritative XP and per-challenge progress."""

from app.domains.progression.access import (
    ChallengeAccess,
    ChallengeProgressionService,
    ChallengeStatus,
)
from app.domains.progression.models import (
    ProgressionResult,
    UserChallengeProgress,
    UserProgressItem,
    UserProgressSummary,
    XPAward,
    XPAwardReason,
    XPRewardConfiguration,
    XPTransaction,
)
from app.domains.progression.ports import UserProgressReader
from app.domains.progression.service import ProgressionService

__all__ = [
    "ChallengeAccess",
    "ChallengeProgressionService",
    "ChallengeStatus",
    "ProgressionResult",
    "ProgressionService",
    "UserChallengeProgress",
    "UserProgressItem",
    "UserProgressReader",
    "UserProgressSummary",
    "XPAward",
    "XPAwardReason",
    "XPRewardConfiguration",
    "XPTransaction",
]
