from typing import Protocol

from app.domains.progression.models import UserProgressSummary


class UserProgressReader(Protocol):
    async def get_summary(self, user_id: str) -> UserProgressSummary: ...
