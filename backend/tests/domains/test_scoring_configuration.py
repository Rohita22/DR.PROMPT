import pytest

from app.domains.scoring.configuration import (
    EfficiencyThresholds,
    ScoringConfiguration,
    StarThresholds,
)
from app.domains.scoring.errors import ScoringConfigurationError


def test_scoring_configuration_represents_weights_and_thresholds() -> None:
    config = ScoringConfiguration(
        accuracy_weight=0.8,
        efficiency_weight=0.2,
        efficiency_thresholds=EfficiencyThresholds(50, 200),
        star_thresholds=StarThresholds(50, 75, 90),
    )

    assert config.accuracy_weight == 0.8
    assert config.efficiency_thresholds.full_credit_at_or_below == 50
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
            efficiency_thresholds=EfficiencyThresholds(50, 200),
            star_thresholds=StarThresholds(50, 75, 90),
        )


@pytest.mark.parametrize(
    ("full_credit", "no_credit"),
    [(-1, 100), (100, 100), (101, 100)],
)
def test_efficiency_thresholds_must_form_an_increasing_range(
    full_credit: int,
    no_credit: int,
) -> None:
    with pytest.raises(ScoringConfigurationError):
        EfficiencyThresholds(full_credit, no_credit)


@pytest.mark.parametrize(
    "thresholds",
    [(75, 50, 90), (-1, 50, 90), (50, 75, 101)],
)
def test_star_thresholds_must_be_ordered_percentages(
    thresholds: tuple[float, float, float],
) -> None:
    with pytest.raises(ScoringConfigurationError):
        StarThresholds(*thresholds)
