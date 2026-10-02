from typing import Protocol

from app.domains.profile.models import ProfileSnapshot


class ProfileReader(Protocol):
    async def get_snapshot(self, user_id: str, *, recent_limit: int) -> ProfileSnapshot: ...
