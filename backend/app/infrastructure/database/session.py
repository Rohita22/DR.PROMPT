from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config.settings import Settings
from app.core.exceptions import PersistenceError


@lru_cache
def _create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, pool_pre_ping=True)


@lru_cache
def _create_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(_create_engine(database_url), expire_on_commit=False)


def create_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    if settings.database_url is None:
        raise PersistenceError("Database configuration is unavailable.")
    return _create_session_factory(settings.database_url.get_secret_value())


def create_database_engine(settings: Settings) -> AsyncEngine:
    if settings.database_url is None:
        raise PersistenceError("Database configuration is unavailable.")
    return _create_engine(settings.database_url.get_secret_value())


async def session_from_factory(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        yield session
