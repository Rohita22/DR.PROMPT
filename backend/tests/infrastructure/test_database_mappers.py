import uuid

import pytest

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
