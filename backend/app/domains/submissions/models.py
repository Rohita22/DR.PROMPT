from dataclasses import dataclass
from datetime import datetime
from math import isfinite

from app.core.exceptions import DomainError


@dataclass(frozen=True, slots=True)
class Submission:
    id: str
    challenge_id: str
    challenge_version_id: str
    user_id: str | None
    prompt: str
    prompt_tokens: int
    passed_tests: int
    total_tests: int
    accuracy: float
    efficiency: float
    final_score: float
    stars: int
    model_identifier: str
    model_configuration_version: str
    created_at: datetime

    def __post_init__(self) -> None:
        identifiers = (self.id, self.challenge_id, self.challenge_version_id)
        if any(not value.strip() for value in identifiers):
            raise DomainError("Submission identifiers cannot be blank.")
        if not self.prompt.strip():
            raise DomainError("Submission prompt cannot be blank.")
        if self.prompt_tokens < 0:
            raise DomainError("Submission prompt token count cannot be negative.")
        if self.total_tests <= 0 or not 0 <= self.passed_tests <= self.total_tests:
            raise DomainError("Submission test counts are invalid.")
        scores = (self.accuracy, self.efficiency, self.final_score)
        if any(not isfinite(score) or not 0 <= score <= 100 for score in scores):
            raise DomainError("Submission scores must be between 0 and 100.")
        if not 0 <= self.stars <= 3:
            raise DomainError("Submission stars must be between 0 and 3.")
        if not self.model_identifier.strip() or not self.model_configuration_version.strip():
            raise DomainError("Submission model metadata cannot be blank.")
        if self.user_id is not None and not self.user_id.strip():
            raise DomainError("Submission user ID cannot be blank when provided.")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise DomainError("Submission timestamp must be timezone-aware.")
