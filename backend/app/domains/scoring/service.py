from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from math import isfinite

from app.domains.scoring.configuration import (
    EfficiencyThresholds,
    ScoringConfiguration,
    StarThresholds,
)
from app.domains.scoring.errors import ScoringInputError

_SCORE_QUANTUM = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class ScoringResult:
    prompt_tokens: int
    accuracy: float
    efficiency: float
    final_score: float
    stars: int


def calculate_efficiency(
    prompt_tokens: int,
    thresholds: EfficiencyThresholds,
) -> float:
    if prompt_tokens < 0:
        raise ScoringInputError("Prompt token count cannot be negative.")
    for tier in thresholds.tiers:
        if prompt_tokens <= tier.max_tokens:
            return tier.score
    return thresholds.score_above_max


def calculate_final_score(
    accuracy: float,
    efficiency: float,
    configuration: ScoringConfiguration,
) -> float:
    _validate_percentage(accuracy, label="Accuracy")
    _validate_percentage(efficiency, label="Efficiency")
    weighted = Decimal(str(accuracy)) * Decimal(str(configuration.accuracy_weight))
    weighted += Decimal(str(efficiency)) * Decimal(str(configuration.efficiency_weight))
    return float(weighted.quantize(_SCORE_QUANTUM, rounding=ROUND_HALF_UP))


def calculate_stars(
    accuracy: float,
    prompt_tokens: int,
    thresholds: StarThresholds,
) -> int:
    _validate_percentage(accuracy, label="Accuracy")
    if prompt_tokens < 0:
        raise ScoringInputError("Prompt token count cannot be negative.")

    three_star_efficiency_met = (
        thresholds.three_star_max_prompt_tokens is None
        or prompt_tokens <= thresholds.three_star_max_prompt_tokens
    )
    if accuracy >= thresholds.three_stars and three_star_efficiency_met:
        return 3
    if accuracy >= thresholds.two_stars:
        return 2
    if accuracy >= thresholds.one_star:
        return 1
    return 0


class ScoringService:
    """Pure challenge-configured scoring calculations."""

    def calculate(
        self,
        *,
        prompt_tokens: int,
        accuracy: float,
        configuration: ScoringConfiguration,
    ) -> ScoringResult:
        efficiency = calculate_efficiency(prompt_tokens, configuration.efficiency_thresholds)
        return ScoringResult(
            prompt_tokens=prompt_tokens,
            accuracy=accuracy,
            efficiency=efficiency,
            final_score=calculate_final_score(accuracy, efficiency, configuration),
            stars=calculate_stars(accuracy, prompt_tokens, configuration.star_thresholds),
        )


def _validate_percentage(value: float, *, label: str) -> None:
    if not isfinite(value) or not 0 <= value <= 100:
        raise ScoringInputError(f"{label} must be a finite percentage from 0 to 100.")
