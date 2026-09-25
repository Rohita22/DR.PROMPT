"""Challenge storage adapters and prototype fixture data."""

from app.infrastructure.challenges.in_memory_hidden_test_repository import (
    InMemoryHiddenTestRepository,
)
from app.infrastructure.challenges.in_memory_repository import InMemoryChallengeRepository

__all__ = ["InMemoryChallengeRepository", "InMemoryHiddenTestRepository"]
