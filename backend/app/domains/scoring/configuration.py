from dataclasses import dataclass
from math import isclose, isfinite

from app.domains.scoring.errors import ScoringConfigurationError


@dataclass(frozen=True, slots=True)
class EfficiencyThresholds:
    """Token counts used by future efficiency scoring, not prompt admission limits."""

    full_credit_at_or_below: int
    no_credit_at_or_above: int

    def __post_init__(self) -> None:
        if self.full_credit_at_or_below < 0:
            raise ScoringConfigurationError("Full-credit token threshold cannot be negative.")
        if self.no_credit_at_or_above <= self.full_credit_at_or_below:
            raise ScoringConfigurationError(
                "No-credit threshold must be greater than the full-credit threshold."
            )


@dataclass(frozen=True, slots=True)
class StarThresholds:
    one_star: float
    two_stars: float
    three_stars: float

    def __post_init__(self) -> None:
        thresholds = (self.one_star, self.two_stars, self.three_stars)
        if any(not isfinite(value) or not 0 <= value <= 100 for value in thresholds):
            raise ScoringConfigurationError("Star thresholds must be between 0 and 100.")
        if thresholds != tuple(sorted(thresholds)):
            raise ScoringConfigurationError("Star thresholds must be non-decreasing.")


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
