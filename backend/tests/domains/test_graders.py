import pytest

from app.domains.evaluation.configuration import (
    AllowedLabelGraderConfig,
    ArrayComparisonGraderConfig,
    CaseInsensitiveExactMatchGraderConfig,
    ExactMatchGraderConfig,
    FieldComparisonGraderConfig,
    JsonSchemaGraderConfig,
)
from app.domains.evaluation.errors import EvaluationConfigurationError
from app.domains.evaluation.graders import (
    AllowedLabelGrader,
    ArrayComparisonGrader,
    CaseInsensitiveExactMatchGrader,
    ExactMatchGrader,
    FieldComparisonGrader,
    JsonSchemaGrader,
)
from app.domains.evaluation.results import FailureReason


def test_exact_match_requires_strict_equality() -> None:
    grader = ExactMatchGrader()
    config = ExactMatchGraderConfig()

    assert grader.grade(expected="billing", actual="billing", config=config).passed
    assert not grader.grade(expected="billing", actual="Billing", config=config).passed
    assert not grader.grade(expected="billing", actual="technical", config=config).passed


@pytest.mark.parametrize("actual", ["Billing", "BILLING", "billing"])
def test_case_insensitive_exact_match_accepts_only_case_variations(actual: str) -> None:
    result = CaseInsensitiveExactMatchGrader().grade(
        expected="billing",
        actual=actual,
        config=CaseInsensitiveExactMatchGraderConfig(),
    )

    assert result.passed


@pytest.mark.parametrize("actual", ["billing issue", " billing", "technical"])
def test_case_insensitive_exact_match_does_not_add_fuzzy_or_whitespace_matching(
    actual: str,
) -> None:
    result = CaseInsensitiveExactMatchGrader().grade(
        expected="billing",
        actual=actual,
        config=CaseInsensitiveExactMatchGraderConfig(),
    )

    assert not result.passed
    assert result.failure_reason is FailureReason.OUTPUT_MISMATCH


def test_allowed_label_validation_is_strict_and_case_sensitive() -> None:
    grader = AllowedLabelGrader()
    config = AllowedLabelGraderConfig(frozenset({"billing", "technical", "account"}))

    assert grader.grade(expected="ignored", actual="billing", config=config).passed
    invalid = grader.grade(expected="ignored", actual="refund", config=config)
    wrong_case = grader.grade(expected="ignored", actual="Billing", config=config)

    assert invalid.failure_reason is FailureReason.INVALID_LABEL
    assert wrong_case.failure_reason is FailureReason.INVALID_LABEL


def test_json_schema_grader_accepts_valid_nested_json() -> None:
    config = JsonSchemaGraderConfig(
        {
            "type": "object",
            "required": ["customer"],
            "properties": {
                "customer": {
                    "type": "object",
                    "required": ["id"],
                    "properties": {"id": {"type": "integer"}},
                }
            },
        }
    )

    result = JsonSchemaGrader().grade(
        expected=None,
        actual='{"customer":{"id":42}}',
        config=config,
    )

    assert result.passed


def test_json_schema_grader_fails_malformed_json_safely() -> None:
    result = JsonSchemaGrader().grade(
        expected=None,
        actual='{"category":',
        config=JsonSchemaGraderConfig({"type": "object"}),
    )

    assert result.failure_reason is FailureReason.INVALID_JSON
    assert result.diagnostic is not None
    assert "category" not in result.diagnostic.message


@pytest.mark.parametrize(
    "actual",
    ['{"count":"two"}', "[]"],
)
def test_json_schema_grader_rejects_schema_violations_and_wrong_types(actual: str) -> None:
    result = JsonSchemaGrader().grade(
        expected=None,
        actual=actual,
        config=JsonSchemaGraderConfig(
            {
                "type": "object",
                "required": ["count"],
                "properties": {"count": {"type": "integer"}},
            }
        ),
    )

    assert result.failure_reason is FailureReason.SCHEMA_VALIDATION_FAILED


def test_json_schema_grader_rejects_invalid_schema_as_configuration_error() -> None:
    with pytest.raises(EvaluationConfigurationError, match="schema is invalid"):
        JsonSchemaGrader().grade(
            expected=None,
            actual="{}",
            config=JsonSchemaGraderConfig({"type": "not-a-json-schema-type"}),
        )


def test_field_comparison_matches_only_configured_fields() -> None:
    result = FieldComparisonGrader().grade(
        expected={"category": "billing", "priority": "high"},
        actual={"category": "billing", "priority": "high", "extra": "ignored"},
        config=FieldComparisonGraderConfig(("category", "priority")),
    )

    assert result.passed


def test_field_comparison_accepts_json_text_and_detects_mismatch() -> None:
    result = FieldComparisonGrader().grade(
        expected={"category": "billing", "priority": "high"},
        actual='{"category":"billing","priority":"low"}',
        config=FieldComparisonGraderConfig(("category", "priority")),
    )

    assert result.failure_reason is FailureReason.FIELD_MISMATCH


def test_field_comparison_detects_missing_actual_field_without_revealing_expected() -> None:
    result = FieldComparisonGrader().grade(
        expected={"category": "secret-answer", "priority": "high"},
        actual={"category": "secret-answer"},
        config=FieldComparisonGraderConfig(("category", "priority")),
    )

    assert result.failure_reason is FailureReason.MISSING_REQUIRED_FIELD
    assert result.diagnostic is not None
    assert "secret-answer" not in result.diagnostic.message


def test_array_comparison_preserves_order_when_configured() -> None:
    grader = ArrayComparisonGrader()
    config = ArrayComparisonGraderConfig(order_matters=True)

    assert grader.grade(expected=["a", "b"], actual='["a","b"]', config=config).passed
    mismatch = grader.grade(expected=["a", "b"], actual=["b", "a"], config=config)
    assert mismatch.failure_reason is FailureReason.ARRAY_MISMATCH


def test_unordered_array_comparison_is_duplicate_count_aware() -> None:
    grader = ArrayComparisonGrader()
    config = ArrayComparisonGraderConfig(order_matters=False)

    assert grader.grade(expected=["a", "a", "b"], actual=["b", "a", "a"], config=config).passed
    mismatch = grader.grade(
        expected=["a", "a", "b"],
        actual=["a", "b", "b"],
        config=config,
    )
    assert mismatch.failure_reason is FailureReason.ARRAY_MISMATCH


def test_array_comparison_rejects_non_array_output_safely() -> None:
    result = ArrayComparisonGrader().grade(
        expected=["a"],
        actual='{"value":"a"}',
        config=ArrayComparisonGraderConfig(),
    )

    assert result.failure_reason is FailureReason.EXPECTED_ARRAY
