import uuid

import pytest

from app.domains.challenges.errors import ChallengeDefinitionError
from app.domains.challenges.models import ChallengeType
from app.domains.evaluation.configuration import (
    AllowedLabelGraderConfig,
    ArrayComparisonGraderConfig,
    CaseInsensitiveExactMatchGraderConfig,
    ExactMatchGraderConfig,
    FieldComparisonGraderConfig,
    JsonSchemaGraderConfig,
)
from app.infrastructure.challenges.in_memory_hidden_test_repository import (
    EXACT_OUTPUT_HIDDEN_TEST_SUITE,
)
from app.infrastructure.challenges.in_memory_repository import EXACT_OUTPUT_CHALLENGE
from app.infrastructure.database.mappers import (
    challenge_type_from_data,
    grader_config_from_data,
    grader_config_to_data,
    hidden_suite_from_rows,
    model_config_from_data,
    model_config_to_data,
    playable_challenge_from_rows,
    scoring_config_from_data,
    scoring_config_to_data,
)
from app.infrastructure.database.models import (
    ChallengeRow,
    ChallengeVersionRow,
    HiddenTestCaseRow,
    VisibleExampleRow,
    VisibleTestCaseRow,
)


def _version_row() -> ChallengeVersionRow:
    version = EXACT_OUTPUT_CHALLENGE.version
    return ChallengeVersionRow(
        id=uuid.uuid4(),
        challenge_id=version.challenge_id,
        version=version.version_id,
        title=version.title,
        description=version.description,
        objective=version.objective,
        constraints=list(version.constraints),
        difficulty=version.difficulty.value,
        prompt_token_limit=version.prompt_token_limit,
        evaluation_config={
            "default_grader": grader_config_to_data(version.evaluation_config.default_grader)
        },
        model_config=model_config_to_data(version.model_config),
        scoring_config=scoring_config_to_data(version.scoring_config),
        publication_state=version.publication_state.value,
        challenge_type=version.challenge_type.value,
    )


def test_persistence_rows_reconstruct_the_public_playable_domain_without_hidden_tests() -> None:
    source = EXACT_OUTPUT_CHALLENGE
    version_row = _version_row()
    challenge_row = ChallengeRow(
        id=source.challenge.id,
        slug=source.challenge.slug,
        track=source.challenge.track.value,
        sort_order=source.challenge.order,
        current_version=source.version.version_id,
    )
    examples = [
        VisibleExampleRow(
            id=uuid.uuid4(),
            challenge_version_id=version_row.id,
            input=example.input,
            expected_output=example.expected_output,
            explanation=example.explanation,
            sort_order=index,
        )
        for index, example in enumerate(source.version.visible_examples, start=1)
    ]
    tests = [
        VisibleTestCaseRow(
            id=uuid.uuid4(),
            challenge_version_id=version_row.id,
            test_id=test.id,
            input=test.input,
            expected_output=test.expected_output,
            evaluation_config=grader_config_to_data(test.grader_config),
            sort_order=index,
        )
        for index, test in enumerate(source.version.visible_test_cases, start=1)
    ]

    reconstructed = playable_challenge_from_rows(challenge_row, version_row, examples, tests)

    assert reconstructed == source
    assert [example.input for example in reconstructed.version.visible_examples] == [
        example.input for example in source.version.visible_examples
    ]
    assert [test.id for test in reconstructed.version.visible_test_cases] == [
        "visible-1",
        "visible-2",
        "visible-3",
    ]
    assert not hasattr(reconstructed, "hidden_test_suite")
    assert not hasattr(reconstructed.version, "hidden_test_cases")


def test_hidden_rows_reconstruct_an_ordered_version_bound_suite() -> None:
    version_row = _version_row()
    rows = [
        HiddenTestCaseRow(
            id=uuid.uuid4(),
            challenge_version_id=version_row.id,
            test_id=test.id,
            input=test.input,
            expected_output=test.expected_output,
            evaluation_config=grader_config_to_data(test.grader_config),
            sort_order=index,
        )
        for index, test in enumerate(EXACT_OUTPUT_HIDDEN_TEST_SUITE.test_cases, start=1)
    ]

    assert hidden_suite_from_rows("1", rows) == EXACT_OUTPUT_HIDDEN_TEST_SUITE
    assert hidden_suite_from_rows("1", []) is None


@pytest.mark.parametrize(
    "configuration",
    [
        ExactMatchGraderConfig(),
        CaseInsensitiveExactMatchGraderConfig(),
        AllowedLabelGraderConfig(frozenset({"yes", "no"})),
        JsonSchemaGraderConfig({"type": "object"}),
        FieldComparisonGraderConfig(("category", "priority")),
        ArrayComparisonGraderConfig(order_matters=False),
    ],
)
def test_all_grader_configurations_round_trip(configuration: object) -> None:
    assert grader_config_from_data(grader_config_to_data(configuration)) == configuration


def test_model_and_scoring_configuration_round_trip() -> None:
    version = EXACT_OUTPUT_CHALLENGE.version

    assert (
        model_config_from_data(model_config_to_data(version.model_config)) == version.model_config
    )
    assert (
        scoring_config_from_data(scoring_config_to_data(version.scoring_config))
        == version.scoring_config
    )

    from app.infrastructure.challenges.application_fixtures import RESPONSIVE_HERO_CHALLENGE

    text_data = model_config_to_data(version.model_config)
    application_data = model_config_to_data(RESPONSIVE_HERO_CHALLENGE.version.model_config)
    assert "reasoning_effort" not in text_data
    assert application_data["reasoning_effort"] == "low"
    assert (
        model_config_from_data(application_data) == RESPONSIVE_HERO_CHALLENGE.version.model_config
    )


def test_challenge_type_round_trips_and_unknown_values_fail() -> None:
    assert _version_row().challenge_type == "text"
    for challenge_type in ChallengeType:
        assert challenge_type_from_data(challenge_type.value) is challenge_type
    with pytest.raises(ChallengeDefinitionError, match="quantum"):
        challenge_type_from_data("quantum")


def test_application_config_round_trips_and_text_versions_store_null() -> None:
    from app.infrastructure.challenges.application_fixtures import RESPONSIVE_HERO_CONFIG
    from app.infrastructure.database.mappers import (
        application_config_from_data,
        application_config_to_data,
    )

    data = application_config_to_data(RESPONSIVE_HERO_CONFIG)
    assert data is not None and data["starter_project"] == "responsive-hero"
    assert application_config_from_data(data) == RESPONSIVE_HERO_CONFIG
    assert application_config_to_data(None) is None
    assert application_config_from_data(None) is None
    assert _version_row().application_config is None
