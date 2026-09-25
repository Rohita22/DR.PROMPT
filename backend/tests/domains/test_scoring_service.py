import pytest

from app.domains.scoring.configuration import (
    EfficiencyThresholds,
    EfficiencyTier,
    ScoringConfiguration,
    StarThresholds,
)
from app.domains.scoring.service import (
    ScoringService,
    calculate_efficiency,
    calculate_final_score,
    calculate_stars,
)


def efficiency_thresholds() -> EfficiencyThresholds:
    return EfficiencyThresholds(
        tiers=(
            EfficiencyTier(60, 100),
            EfficiencyTier(100, 90),
            EfficiencyTier(150, 75),
            EfficiencyTier(250, 60),
        ),
        score_above_max=40,
    )


def scoring_configuration(
    *,
    accuracy_weight: float = 0.8,
    efficiency_weight: float = 0.2,
    star_thresholds: StarThresholds | None = None,
) -> ScoringConfiguration:
    return ScoringConfiguration(
        accuracy_weight=accuracy_weight,
        efficiency_weight=efficiency_weight,
        efficiency_thresholds=efficiency_thresholds(),
        star_thresholds=star_thresholds or StarThresholds(70, 90, 100, 60),
    )


@pytest.mark.parametrize(
    ("prompt_tokens", "expected"),
    [
        (0, 100),
        (59, 100),
        (60, 100),
        (61, 90),
        (100, 90),
        (101, 75),
        (150, 75),
        (151, 60),
        (250, 60),
        (251, 40),
        (10_000, 40),
    ],
)
def test_efficiency_uses_inclusive_configured_boundaries(
    prompt_tokens: int,
    expected: float,
) -> None:
    assert calculate_efficiency(prompt_tokens, efficiency_thresholds()) == expected


@pytest.mark.parametrize(
    ("accuracy", "efficiency", "config", "expected"),
    [
        (90, 75, scoring_configuration(), 87.0),
        (100, 100, scoring_configuration(), 100.0),
        (0, 100, scoring_configuration(), 20.0),
        (83.33333333333333, 100, scoring_configuration(), 86.67),
        (90, 60, scoring_configuration(accuracy_weight=0.5, efficiency_weight=0.5), 75.0),
    ],
)
def test_final_score_uses_configured_weights_and_half_up_rounding(
    accuracy: float,
    efficiency: float,
    config: ScoringConfiguration,
    expected: float,
) -> None:
    assert calculate_final_score(accuracy, efficiency, config) == expected


@pytest.mark.parametrize(
    ("accuracy", "prompt_tokens", "expected"),
    [
        (69.99, 20, 0),
        (70, 20, 1),
        (90, 20, 2),
        (100, 61, 2),
        (100, 60, 3),
    ],
)
def test_stars_use_accuracy_and_inclusive_three_star_efficiency_boundary(
    accuracy: float,
    prompt_tokens: int,
    expected: int,
) -> None:
    assert calculate_stars(accuracy, prompt_tokens, StarThresholds(70, 90, 100, 60)) == expected


def test_three_stars_can_be_configured_without_an_efficiency_requirement() -> None:
    assert calculate_stars(100, 1_000, StarThresholds(70, 90, 100)) == 3


def test_challenge_specific_star_thresholds_are_honored() -> None:
    thresholds = StarThresholds(50, 75, 95, three_star_max_prompt_tokens=25)

    assert calculate_stars(49, 10, thresholds) == 0
    assert calculate_stars(50, 10, thresholds) == 1
    assert calculate_stars(75, 10, thresholds) == 2
    assert calculate_stars(95, 25, thresholds) == 3
    assert calculate_stars(95, 26, thresholds) == 2


def test_scoring_service_returns_one_cohesive_result() -> None:
    result = ScoringService().calculate(
        prompt_tokens=42,
        accuracy=90,
        configuration=scoring_configuration(),
    )

    assert result.prompt_tokens == 42
    assert result.accuracy == 90
    assert result.efficiency == 100
    assert result.final_score == 92
    assert result.stars == 2
