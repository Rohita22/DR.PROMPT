from dataclasses import dataclass
from math import isclose, isfinite

from app.domains.scoring.errors import ScoringConfigurationError


@dataclass(frozen=True, slots=True)
class EfficiencyTier:
    max_tokens: int
    score: float

    def __post_init__(self) -> None:
        if self.max_tokens < 0:
            raise ScoringConfigurationError("Efficiency tier token limits cannot be negative.")
        if not isfinite(self.score) or not 0 <= self.score <= 100:
            raise ScoringConfigurationError("Efficiency tier scores must be between 0 and 100.")


@dataclass(frozen=True, slots=True)
class EfficiencyThresholds:
    """Inclusive token ceilings and scores, separate from prompt admission limits."""

    tiers: tuple[EfficiencyTier, ...]
    score_above_max: float

    def __post_init__(self) -> None:
        tiers = tuple(self.tiers)
        if not tiers:
            raise ScoringConfigurationError("Efficiency thresholds require at least one tier.")
        token_limits = tuple(tier.max_tokens for tier in tiers)
        if any(
            current >= following
            for current, following in zip(token_limits, token_limits[1:], strict=False)
        ):
            raise ScoringConfigurationError(
                "Efficiency tier token limits must be strictly increasing."
            )
        scores = tuple(tier.score for tier in tiers)
        if any(current < following for current, following in zip(scores, scores[1:], strict=False)):
            raise ScoringConfigurationError("Efficiency tier scores must be non-increasing.")
        if not isfinite(self.score_above_max) or not 0 <= self.score_above_max <= 100:
            raise ScoringConfigurationError("The above-maximum efficiency score must be 0 to 100.")
        if self.score_above_max > scores[-1]:
            raise ScoringConfigurationError(
                "The above-maximum score cannot exceed the final efficiency tier score."
            )
        object.__setattr__(self, "tiers", tiers)


@dataclass(frozen=True, slots=True)
class StarThresholds:
    one_star: float
    two_stars: float
    three_stars: float
    three_star_max_prompt_tokens: int | None = None

    def __post_init__(self) -> None:
        thresholds = (self.one_star, self.two_stars, self.three_stars)
        if any(not isfinite(value) or not 0 <= value <= 100 for value in thresholds):
            raise ScoringConfigurationError("Star thresholds must be between 0 and 100.")
        if thresholds != tuple(sorted(thresholds)):
            raise ScoringConfigurationError("Star thresholds must be non-decreasing.")
        if self.three_star_max_prompt_tokens is not None and self.three_star_max_prompt_tokens < 0:
            raise ScoringConfigurationError("The three-star prompt-token limit cannot be negative.")


@dataclass(frozen=True, slots=True)
class ScoringConfiguration:
    accuracy_weight: float
    efficiency_weight: float
    efficiency_thresholds: EfficiencyThresholds
    star_thresholds: StarThresholds

    def __post_init__(self) -> None:
        weights = (self.accuracy_weight, self.efficiency_weight)
        if any(not isfinite(weight) or weight < 0 for weight in weights):
            raise ScoringConfigurationError("Scoring weights must be finite and non-negative.")
        if not isclose(sum(weights), 1.0, abs_tol=1e-9):
            raise ScoringConfigurationError("Scoring weights must sum to 1.")
