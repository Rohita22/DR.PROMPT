import pytest

from app.domains.evaluation.configuration import (
    AllowedLabelGraderConfig,
    ArrayComparisonGraderConfig,
    CaseInsensitiveExactMatchGraderConfig,
    ExactMatchGraderConfig,
    FieldComparisonGraderConfig,
    GraderType,
    JsonSchemaGraderConfig,
    ModelConfiguration,
)
from app.domains.evaluation.errors import EvaluationConfigurationError
from app.domains.evaluation.graders import ExactMatchGrader
from app.domains.evaluation.ports import Grader
from app.domains.evaluation.results import (
    EvaluationResult,
    FailureReason,
    GradeResult,
    SafeDiagnostic,
)
from app.domains.evaluation.results import (
    TestEvaluationResult as CaseEvaluationResult,
)
from app.domains.evaluation.test_cases import HiddenTestCase, HiddenTestSuite, VisibleTestCase


def test_all_planned_grader_types_have_typed_configuration() -> None:
    configurations = (
        ExactMatchGraderConfig(),
        CaseInsensitiveExactMatchGraderConfig(),
        AllowedLabelGraderConfig(frozenset({"billing", "account"})),
        JsonSchemaGraderConfig({"type": "object"}),
        FieldComparisonGraderConfig(("category", "priority")),
        ArrayComparisonGraderConfig(order_matters=False),
    )

    assert {config.grader_type for config in configurations} == set(GraderType)


@pytest.mark.parametrize(
    "labels",
    [frozenset(), frozenset({""}), frozenset({"billing", " billing "})],
)
def test_allowed_label_configuration_requires_unique_non_blank_labels(
    labels: frozenset[str],
) -> None:
    with pytest.raises(EvaluationConfigurationError):
        AllowedLabelGraderConfig(labels)


def test_model_configuration_is_provider_neutral_and_normalized() -> None:
    config = ModelConfiguration(
        model_id="  provider-independent/model-v1  ",
        temperature=0.5,
        max_output_tokens=128,
        configuration_version="  config-v2 ",
        system_wrapper="  Follow the player prompt.  ",
    )

    assert config.model_id == "provider-independent/model-v1"
    assert config.configuration_version == "config-v2"
    assert config.system_wrapper == "Follow the player prompt."


@pytest.mark.parametrize("temperature", [-0.01, 2.01, float("inf"), float("nan")])
def test_model_configuration_rejects_invalid_temperature(temperature: float) -> None:
    with pytest.raises(EvaluationConfigurationError, match="Temperature"):
        ModelConfiguration(
            model_id="model-v1",
            temperature=temperature,
            max_output_tokens=128,
            configuration_version="v1",
        )


@pytest.mark.parametrize("max_output_tokens", [0, -1])
def test_model_configuration_requires_positive_output_limit(max_output_tokens: int) -> None:
    with pytest.raises(EvaluationConfigurationError, match="max output tokens"):
        ModelConfiguration(
            model_id="model-v1",
            temperature=0,
            max_output_tokens=max_output_tokens,
            configuration_version="v1",
        )


def test_visible_and_hidden_test_cases_are_distinct_domain_types() -> None:
    config = ExactMatchGraderConfig()
    visible = VisibleTestCase("visible-1", "input", "answer", config)
    hidden = HiddenTestCase("hidden-1", "input", "answer", config)

    assert type(visible) is VisibleTestCase
    assert type(hidden) is HiddenTestCase
    assert not isinstance(hidden, VisibleTestCase)


def test_hidden_test_suite_requires_unique_cases() -> None:
    case = HiddenTestCase("hidden-1", "input", "answer", ExactMatchGraderConfig())

    with pytest.raises(EvaluationConfigurationError, match="must be unique"):
        HiddenTestSuite("challenge-1:v1", (case, case))


def test_exact_match_grader_satisfies_contract_and_is_case_sensitive() -> None:
    grader: Grader[ExactMatchGraderConfig] = ExactMatchGrader()
    config = ExactMatchGraderConfig()

    passed = grader.grade(expected="billing", actual="billing", config=config)
    failed = grader.grade(expected="billing", actual="Billing", config=config)

    assert passed == GradeResult(passed=True)
    assert failed.passed is False
    assert failed.failure_reason is FailureReason.OUTPUT_MISMATCH
    assert failed.diagnostic is not None
    assert failed.diagnostic.code == "output_mismatch"
    assert "billing" not in failed.diagnostic.message.lower()


def test_safe_diagnostic_does_not_carry_expected_or_actual_values() -> None:
    diagnostic = SafeDiagnostic(code="invalid_output", message="Output could not be parsed.")

    assert vars(type(diagnostic))["__slots__"] == ("code", "message")


def test_passing_grade_cannot_include_failure_information() -> None:
    with pytest.raises(EvaluationConfigurationError, match="passing grade"):
        GradeResult(
            passed=True,
            failure_reason=FailureReason.OUTPUT_MISMATCH,
        )


def test_aggregate_evaluation_calculates_counts_and_accuracy() -> None:
    result = EvaluationResult(
        test_results=(
            CaseEvaluationResult("test-1", GradeResult(passed=True)),
            CaseEvaluationResult(
                "test-2",
                GradeResult(passed=False, failure_reason=FailureReason.INVALID_OUTPUT),
            ),
            CaseEvaluationResult("test-3", GradeResult(passed=True)),
        )
    )

    assert result.passed_count == 2
    assert result.total_count == 3
    assert result.accuracy == pytest.approx(200 / 3)


def test_aggregate_evaluation_rejects_empty_or_duplicate_results() -> None:
    with pytest.raises(EvaluationConfigurationError, match="at least one test"):
        EvaluationResult(())

    repeated = CaseEvaluationResult("test-1", GradeResult(passed=True))
    with pytest.raises(EvaluationConfigurationError, match="must be unique"):
        EvaluationResult((repeated, repeated))
