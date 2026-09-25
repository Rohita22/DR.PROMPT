from dataclasses import FrozenInstanceError, fields

import pytest

from app.domains.challenges.errors import ChallengeDefinitionError
from app.domains.challenges.models import (
    Challenge,
    ChallengeTrack,
    ChallengeVersion,
    Difficulty,
    PublicationState,
    VisibleExample,
)
from app.domains.evaluation.configuration import (
    EvaluationConfiguration,
    ExactMatchGraderConfig,
    ModelConfiguration,
)
from app.domains.evaluation.test_cases import HiddenTestCase, HiddenTestSuite, VisibleTestCase
from app.domains.scoring.configuration import (
    EfficiencyThresholds,
    EfficiencyTier,
    ScoringConfiguration,
    StarThresholds,
)


def scoring_config() -> ScoringConfiguration:
    return ScoringConfiguration(
        accuracy_weight=0.8,
        efficiency_weight=0.2,
        efficiency_thresholds=EfficiencyThresholds(
            tiers=(EfficiencyTier(max_tokens=50, score=100), EfficiencyTier(200, 40)),
            score_above_max=20,
        ),
        star_thresholds=StarThresholds(one_star=50, two_stars=75, three_stars=90),
    )


def model_config() -> ModelConfiguration:
    return ModelConfiguration(
        model_id="model-family/model-version",
        temperature=0.2,
        max_output_tokens=256,
        configuration_version="v1",
    )


def visible_test(test_id: str = "visible-1") -> VisibleTestCase:
    return VisibleTestCase(
        id=test_id,
        input="Route this request: I need an invoice",
        expected_output="billing",
        grader_config=ExactMatchGraderConfig(),
    )


def challenge_version(**overrides: object) -> ChallengeVersion:
    values: dict[str, object] = {
        "version_id": "challenge-1:v1",
        "challenge_id": "challenge-1",
        "title": "Route the request",
        "description": "Classify support requests into the correct queue.",
        "objective": "Return exactly one routing label.",
        "constraints": ("Return one label", "Do not add prose"),
        "difficulty": Difficulty.EASY,
        "visible_examples": (
            VisibleExample(
                input="I was charged twice",
                expected_output="billing",
                explanation="Duplicate charges belong to billing.",
            ),
        ),
        "visible_test_cases": (visible_test(),),
        "prompt_token_limit": 250,
        "evaluation_config": EvaluationConfiguration(default_grader=ExactMatchGraderConfig()),
        "scoring_config": scoring_config(),
        "model_config": model_config(),
        "publication_state": PublicationState.PUBLISHED,
    }
    values.update(overrides)
    return ChallengeVersion(**values)  # type: ignore[arg-type]


def test_constructs_stable_challenge_identity() -> None:
    challenge = Challenge(
        id="challenge-1",
        slug="route-support-request",
        track=ChallengeTrack.CLASSIFY,
        order=3,
        current_version_id="challenge-1:v2",
    )

    assert challenge.slug == "route-support-request"
    assert challenge.track is ChallengeTrack.CLASSIFY
    assert challenge.current_version_id == "challenge-1:v2"


@pytest.mark.parametrize("slug", ["", "Route-Request", "route_request", "route--request"])
def test_rejects_invalid_challenge_slugs(slug: str) -> None:
    with pytest.raises(ChallengeDefinitionError):
        Challenge(id="challenge-1", slug=slug, track=ChallengeTrack.CONTROL, order=0)


def test_challenge_value_objects_are_immutable() -> None:
    challenge = Challenge(
        id="challenge-1", slug="challenge-one", track=ChallengeTrack.EXTRACT, order=1
    )

    with pytest.raises(FrozenInstanceError):
        challenge.order = 2  # type: ignore[misc]


def test_constructs_exact_playable_challenge_version() -> None:
    version = challenge_version()

    assert version.challenge_id == "challenge-1"
    assert version.difficulty is Difficulty.EASY
    assert version.publication_state is PublicationState.PUBLISHED
    assert version.visible_examples[0].explanation == "Duplicate charges belong to billing."
    assert version.visible_test_cases[0].id == "visible-1"
    assert version.prompt_token_limit == 250


def test_visible_examples_are_not_executable_test_cases() -> None:
    version = challenge_version()

    assert isinstance(version.visible_examples[0], VisibleExample)
    assert not isinstance(version.visible_examples[0], VisibleTestCase)


def test_hidden_cases_are_kept_outside_challenge_version() -> None:
    hidden_case = HiddenTestCase(
        id="hidden-1",
        input="Please change my password",
        expected_output="account",
        grader_config=ExactMatchGraderConfig(),
    )
    suite = HiddenTestSuite(
        challenge_version_id="challenge-1:v1",
        test_cases=(hidden_case,),
    )

    assert suite.challenge_version_id == "challenge-1:v1"
    assert type(suite.test_cases[0]) is HiddenTestCase
    assert type(visible_test()) is VisibleTestCase
    assert "hidden_test_cases" not in {field.name for field in fields(ChallengeVersion)}


def test_published_version_requires_a_visible_test() -> None:
    with pytest.raises(ChallengeDefinitionError, match="requires a visible test"):
        challenge_version(visible_test_cases=())


def test_draft_version_may_be_prepared_before_tests_exist() -> None:
    version = challenge_version(
        visible_test_cases=(),
        publication_state=PublicationState.DRAFT,
    )

    assert version.visible_test_cases == ()


@pytest.mark.parametrize("prompt_token_limit", [0, -1])
def test_rejects_non_positive_prompt_token_limits(prompt_token_limit: int) -> None:
    with pytest.raises(ChallengeDefinitionError, match="Prompt token limit"):
        challenge_version(prompt_token_limit=prompt_token_limit)


def test_keeps_efficiency_thresholds_within_hard_prompt_limit() -> None:
    with pytest.raises(ChallengeDefinitionError, match="Efficiency thresholds"):
        challenge_version(prompt_token_limit=150)


def test_rejects_duplicate_visible_test_ids() -> None:
    with pytest.raises(ChallengeDefinitionError, match="test-case IDs must be unique"):
        challenge_version(visible_test_cases=(visible_test(), visible_test()))
