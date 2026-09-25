from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config.settings import Settings
from app.core.exceptions import PersistenceError


@lru_cache
def _create_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    return async_sessionmaker(engine, expire_on_commit=False)


def create_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    if settings.database_url is None:
        raise PersistenceError("Database configuration is unavailable.")
    return _create_session_factory(settings.database_url.get_secret_value())


async def session_from_factory(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        yield session
