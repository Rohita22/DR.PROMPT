"""Persistence adapters (none implemented yet)."""

from app.infrastructure.database.models import Base
from app.infrastructure.database.repositories import (
    PostgresChallengeRepository,
    PostgresHiddenTestSuiteRepository,
    PostgresSubmissionRepository,
    PostgresUserProgressRepository,
)
from app.infrastructure.database.session import create_session_factory
from app.infrastructure.database.user_repository import PostgresUserRepository

__all__ = [
    "Base",
    "PostgresChallengeRepository",
    "PostgresHiddenTestSuiteRepository",
    "PostgresSubmissionRepository",
    "PostgresUserProgressRepository",
    "PostgresUserRepository",
    "create_session_factory",
]
