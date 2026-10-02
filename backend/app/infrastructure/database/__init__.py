"""Persistence adapters (none implemented yet)."""

from app.infrastructure.database.admin_repository import PostgresAdminChallengeRepository
from app.infrastructure.database.leaderboard_repository import PostgresLeaderboardRepository
from app.infrastructure.database.models import Base
from app.infrastructure.database.profile_repository import PostgresProfileRepository
from app.infrastructure.database.repositories import (
    PostgresChallengeRepository,
    PostgresChallengeWriter,
    PostgresHiddenTestSuiteRepository,
    PostgresSubmissionRepository,
    PostgresUserProgressRepository,
)
from app.infrastructure.database.session import create_database_engine, create_session_factory
from app.infrastructure.database.user_repository import PostgresUserRepository

__all__ = [
    "Base",
    "PostgresAdminChallengeRepository",
    "PostgresChallengeRepository",
    "PostgresChallengeWriter",
    "PostgresHiddenTestSuiteRepository",
    "PostgresLeaderboardRepository",
    "PostgresProfileRepository",
    "PostgresSubmissionRepository",
    "PostgresUserProgressRepository",
    "PostgresUserRepository",
    "create_session_factory",
    "create_database_engine",
]
