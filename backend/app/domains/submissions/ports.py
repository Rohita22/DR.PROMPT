from typing import Protocol

from app.domains.challenges.models import Difficulty
from app.domains.progression.models import ProgressionResult, XPRewardConfiguration
from app.domains.submissions.models import Submission


class SubmissionRepository(Protocol):
    async def save_with_progression(
        self,
        submission: Submission,
        *,
        difficulty: Difficulty,
        xp_configuration: XPRewardConfiguration,
    ) -> ProgressionResult: ...
