import pytest

from app.domains.scoring.configuration import (
    EfficiencyThresholds,
    EfficiencyTier,
    ScoringConfiguration,
    StarThresholds,
)
from app.domains.scoring.errors import ScoringConfigurationError


def efficiency_thresholds() -> EfficiencyThresholds:
    return EfficiencyThresholds(
        tiers=(EfficiencyTier(50, 100), EfficiencyTier(200, 40)),
        score_above_max=20,
    )


def test_scoring_configuration_represents_weights_and_thresholds() -> None:
    config = ScoringConfiguration(
        accuracy_weight=0.8,
        efficiency_weight=0.2,
        efficiency_thresholds=efficiency_thresholds(),
        star_thresholds=StarThresholds(50, 75, 90),
    )

    assert config.accuracy_weight == 0.8
    assert config.efficiency_thresholds.tiers[0].max_tokens == 50
    assert config.star_thresholds.three_stars == 90


@pytest.mark.parametrize(
    ("accuracy_weight", "efficiency_weight"),
    [(0.8, 0.3), (-0.1, 1.1), (float("nan"), 0.2)],
)
def test_scoring_weights_must_be_finite_non_negative_and_sum_to_one(
    accuracy_weight: float,
    efficiency_weight: float,
) -> None:
    with pytest.raises(ScoringConfigurationError):
        ScoringConfiguration(
            accuracy_weight=accuracy_weight,
            efficiency_weight=efficiency_weight,
            efficiency_thresholds=efficiency_thresholds(),
            star_thresholds=StarThresholds(50, 75, 90),
        )


@pytest.mark.parametrize("limits", [(100, 100), (101, 100)])
def test_efficiency_tier_limits_must_be_strictly_increasing(
    limits: tuple[int, int],
) -> None:
    with pytest.raises(ScoringConfigurationError):
        EfficiencyThresholds(
            tiers=(EfficiencyTier(limits[0], 100), EfficiencyTier(limits[1], 80)),
            score_above_max=40,
        )


def test_efficiency_thresholds_require_at_least_one_tier() -> None:
    with pytest.raises(ScoringConfigurationError):
        EfficiencyThresholds(tiers=(), score_above_max=0)


def test_efficiency_scores_must_not_increase_with_longer_prompts() -> None:
    with pytest.raises(ScoringConfigurationError):
        EfficiencyThresholds(
            tiers=(EfficiencyTier(50, 80), EfficiencyTier(100, 90)),
            score_above_max=40,
        )


@pytest.mark.parametrize(
    ("max_tokens", "score"),
    [(-1, 100), (10, -1), (10, 101)],
)
def test_efficiency_tier_values_are_valid(max_tokens: int, score: float) -> None:
    with pytest.raises(ScoringConfigurationError):
        EfficiencyTier(max_tokens, score)


@pytest.mark.parametrize(
    "thresholds",
    [(75, 50, 90), (-1, 50, 90), (50, 75, 101)],
)
def test_star_thresholds_must_be_ordered_percentages(
    thresholds: tuple[float, float, float],
) -> None:
    with pytest.raises(ScoringConfigurationError):
        StarThresholds(*thresholds)


def test_three_star_prompt_limit_cannot_be_negative() -> None:
    with pytest.raises(ScoringConfigurationError):
        StarThresholds(70, 90, 100, three_star_max_prompt_tokens=-1)
