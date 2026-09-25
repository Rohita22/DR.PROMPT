import re
from dataclasses import dataclass
from enum import StrEnum

from app.domains.challenges.errors import ChallengeDefinitionError
from app.domains.evaluation.configuration import EvaluationConfiguration, ModelConfiguration
from app.domains.evaluation.test_cases import VisibleTestCase
from app.domains.evaluation.types import EvaluationValue
from app.domains.scoring.configuration import ScoringConfiguration

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ChallengeTrack(StrEnum):
    CONTROL = "control"
    EXTRACT = "extract"
    CLASSIFY = "classify"
    STRUCTURE = "structure"


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    BOSS = "boss"


class PublicationState(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    RETIRED = "retired"


def _required_text(value: str, *, label: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ChallengeDefinitionError(f"{label} cannot be blank.")
    return normalized


@dataclass(frozen=True, slots=True)
class Challenge:
    """Stable challenge identity independent of any playable version."""

    id: str
    slug: str
    track: ChallengeTrack
    order: int
    current_version_id: str | None = None

    def __post_init__(self) -> None:
        challenge_id = _required_text(self.id, label="Challenge ID")
        slug = _required_text(self.slug, label="Challenge slug")
        if not _SLUG_PATTERN.fullmatch(slug):
            raise ChallengeDefinitionError(
                "Challenge slug must use lowercase letters, numbers, and single hyphens."
            )
        if self.order < 0:
            raise ChallengeDefinitionError("Challenge order cannot be negative.")
        if self.current_version_id is not None:
            current_version_id = _required_text(
                self.current_version_id,
                label="Current version ID",
            )
            object.__setattr__(self, "current_version_id", current_version_id)
        object.__setattr__(self, "id", challenge_id)
        object.__setattr__(self, "slug", slug)


@dataclass(frozen=True, slots=True)
class VisibleExample:
    """Explanatory content; it is not automatically an executable test."""

    input: EvaluationValue
    expected_output: EvaluationValue
    explanation: str | None = None

    def __post_init__(self) -> None:
        if self.explanation is not None:
            explanation = _required_text(self.explanation, label="Example explanation")
            object.__setattr__(self, "explanation", explanation)


@dataclass(frozen=True, slots=True)
class ChallengeVersion:
    """Exact playable definition used to attribute future submissions."""

    version_id: str
    challenge_id: str
    title: str
    description: str
    objective: str
    constraints: tuple[str, ...]
    difficulty: Difficulty
    visible_examples: tuple[VisibleExample, ...]
    visible_test_cases: tuple[VisibleTestCase, ...]
    prompt_token_limit: int | None
    evaluation_config: EvaluationConfiguration
    scoring_config: ScoringConfiguration
    model_config: ModelConfiguration
    publication_state: PublicationState = PublicationState.DRAFT

    def __post_init__(self) -> None:
        for attribute, label in (
            ("version_id", "Challenge version ID"),
            ("challenge_id", "Challenge ID"),
            ("title", "Challenge title"),
            ("description", "Challenge description"),
            ("objective", "Challenge objective"),
        ):
            object.__setattr__(
                self,
                attribute,
                _required_text(getattr(self, attribute), label=label),
            )

        constraints = tuple(constraint.strip() for constraint in self.constraints)
        if any(not constraint for constraint in constraints):
            raise ChallengeDefinitionError("Challenge constraints cannot contain blank values.")
        if len(set(constraints)) != len(constraints):
            raise ChallengeDefinitionError("Challenge constraints must be unique.")
        object.__setattr__(self, "constraints", constraints)
        object.__setattr__(self, "visible_examples", tuple(self.visible_examples))
        object.__setattr__(self, "visible_test_cases", tuple(self.visible_test_cases))

        if self.prompt_token_limit is not None and self.prompt_token_limit <= 0:
            raise ChallengeDefinitionError("Prompt token limit must be positive when provided.")
        if (
            self.prompt_token_limit is not None
            and self.scoring_config.efficiency_thresholds.tiers[-1].max_tokens
            > self.prompt_token_limit
        ):
            raise ChallengeDefinitionError(
                "Efficiency thresholds cannot extend beyond the prompt token limit."
            )

        test_ids = tuple(test_case.id for test_case in self.visible_test_cases)
        if len(set(test_ids)) != len(test_ids):
            raise ChallengeDefinitionError("Visible test-case IDs must be unique.")
        if self.publication_state is PublicationState.PUBLISHED and not self.visible_test_cases:
            raise ChallengeDefinitionError("A published challenge requires a visible test case.")


@dataclass(frozen=True, slots=True)
class PlayableChallenge:
    """A stable challenge identity paired with its current published version."""

    challenge: Challenge
    version: ChallengeVersion

    def __post_init__(self) -> None:
        if self.version.challenge_id != self.challenge.id:
            raise ChallengeDefinitionError("Challenge version belongs to a different challenge.")
        if self.challenge.current_version_id != self.version.version_id:
            raise ChallengeDefinitionError("Challenge does not reference the supplied version.")
        if self.version.publication_state is not PublicationState.PUBLISHED:
            raise ChallengeDefinitionError("A playable challenge version must be published.")
