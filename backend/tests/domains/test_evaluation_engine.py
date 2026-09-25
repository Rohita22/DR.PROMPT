import pytest

from app.domains.evaluation.configuration import (
    AllowedLabelGraderConfig,
    ArrayComparisonGraderConfig,
    CaseInsensitiveExactMatchGraderConfig,
    ExactMatchGraderConfig,
    FieldComparisonGraderConfig,
    GraderType,
    JsonSchemaGraderConfig,
)
from app.domains.evaluation.engine import EvaluationEngine
from app.domains.evaluation.errors import (
    EvaluationBatchError,
    EvaluationConfigurationError,
    UnsupportedGraderError,
)
from app.domains.evaluation.graders import ExactMatchGrader
from app.domains.evaluation.registry import GraderRegistry
from app.domains.evaluation.results import FailureReason
from app.domains.evaluation.test_cases import HiddenTestCase, VisibleTestCase


def visible_case(
    test_id: str,
    expected: str = "billing",
) -> VisibleTestCase:
    return VisibleTestCase(
        id=test_id,
        input="Classify this request",
        expected_output=expected,
        grader_config=ExactMatchGraderConfig(),
    )


def test_default_registry_resolves_every_builtin_grader_type() -> None:
    registry = GraderRegistry.with_builtins()
    cases = (
        (ExactMatchGraderConfig(), "billing", "billing"),
        (CaseInsensitiveExactMatchGraderConfig(), "billing", "BILLING"),
        (AllowedLabelGraderConfig(frozenset({"billing"})), None, "billing"),
        (JsonSchemaGraderConfig({"type": "object"}), None, "{}"),
        (FieldComparisonGraderConfig(("category",)), {"category": "a"}, {"category": "a"}),
        (ArrayComparisonGraderConfig(), ["a"], ["a"]),
    )

    assert {config.grader_type for config, _, _ in cases} == set(GraderType)
    for config, expected, actual in cases:
        result = registry.resolve(config).grade(
            expected=expected,
            actual=actual,
            config=config,
        )
        assert result.passed


def test_registry_fails_predictably_for_unregistered_grader() -> None:
    with pytest.raises(UnsupportedGraderError, match="No grader is registered"):
        GraderRegistry().resolve(ExactMatchGraderConfig())


def test_registry_instances_do_not_share_mutable_state() -> None:
    configured = GraderRegistry.with_builtins()
    empty = GraderRegistry()

    assert configured.resolve(ExactMatchGraderConfig()) is not None
    with pytest.raises(UnsupportedGraderError):
        empty.resolve(ExactMatchGraderConfig())


def test_registry_rejects_duplicate_registration() -> None:
    registry = GraderRegistry()
    registry.register(
        grader_type=GraderType.EXACT_MATCH,
        config_type=ExactMatchGraderConfig,
        grader=ExactMatchGrader(),
    )

    with pytest.raises(EvaluationConfigurationError, match="already registered"):
        registry.register(
            grader_type=GraderType.EXACT_MATCH,
            config_type=ExactMatchGraderConfig,
            grader=ExactMatchGrader(),
        )


def test_engine_evaluates_one_test() -> None:
    result = EvaluationEngine.with_builtin_graders().evaluate_test(
        visible_case("visible-1"),
        "billing",
    )

    assert result.test_case_id == "visible-1"
    assert result.grade.passed


def test_engine_associates_batch_outputs_by_test_identifier() -> None:
    engine = EvaluationEngine.with_builtin_graders()
    cases = (visible_case("test-a", "billing"), visible_case("test-b", "technical"))

    result = engine.evaluate_batch(
        cases,
        {"test-b": "technical", "test-a": "wrong"},
    )

    assert [item.test_case_id for item in result.test_results] == ["test-a", "test-b"]
    assert result.passed_count == 1
    assert result.total_count == 2
    assert result.accuracy == 50.0


def test_missing_output_is_a_deterministic_grade_failure() -> None:
    result = EvaluationEngine.with_builtin_graders().evaluate_batch(
        (visible_case("test-a"), visible_case("test-b")),
        {"test-a": "billing"},
    )

    assert result.passed_count == 1
    assert result.test_results[1].grade.failure_reason is FailureReason.MISSING_OUTPUT


def test_unknown_output_identifier_rejects_malformed_batch() -> None:
    with pytest.raises(EvaluationBatchError, match="unknown test-case IDs"):
        EvaluationEngine.with_builtin_graders().evaluate_batch(
            (visible_case("test-a"),),
            {"test-a": "billing", "not-a-test": "output"},
        )


def test_duplicate_or_empty_test_collection_is_rejected() -> None:
    engine = EvaluationEngine.with_builtin_graders()
    duplicate = visible_case("test-a")

    with pytest.raises(EvaluationBatchError, match="IDs must be unique"):
        engine.evaluate_batch((duplicate, duplicate), {"test-a": "billing"})
    with pytest.raises(EvaluationBatchError, match="empty test collection"):
        engine.evaluate_batch((), {})


def test_engine_handles_hidden_cases_without_putting_answers_in_results() -> None:
    hidden = HiddenTestCase(
        id="hidden-1",
        input="secret input",
        expected_output="secret-expected-answer",
        grader_config=ExactMatchGraderConfig(),
    )

    result = EvaluationEngine.with_builtin_graders().evaluate_test(hidden, "wrong")

    assert result.grade.diagnostic is not None
    assert "secret-expected-answer" not in result.grade.diagnostic.message
    assert not hasattr(result, "expected_output")
