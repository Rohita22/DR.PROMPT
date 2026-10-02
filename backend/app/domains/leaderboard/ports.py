from typing import Protocol

from app.domains.leaderboard.models import LeaderboardPage


class LeaderboardReader(Protocol):
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
    ) -> LeaderboardPage: ...
