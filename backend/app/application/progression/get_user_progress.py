from app.domains.progression import UserProgressReader, UserProgressSummary


class GetUserProgressUseCase:
    def __init__(self, reader: UserProgressReader) -> None:
        self._reader = reader

    async def execute(self, user_id: str) -> UserProgressSummary:
        return await self._reader.get_summary(user_id)
