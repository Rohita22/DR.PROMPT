from collections.abc import Mapping, Sequence

from app.domains.evaluation.errors import EvaluationBatchError
from app.domains.evaluation.registry import GraderRegistry
from app.domains.evaluation.results import (
    EvaluationResult,
    FailureReason,
    GradeResult,
    SafeDiagnostic,
    TestEvaluationResult,
)
from app.domains.evaluation.test_cases import HiddenTestCase, VisibleTestCase
from app.domains.evaluation.types import EvaluationValue

type ExecutableTestCase = VisibleTestCase | HiddenTestCase


class EvaluationEngine:
    """Grades already-produced outputs; it never executes a model."""

    def __init__(self, registry: GraderRegistry) -> None:
        self._registry = registry

    @classmethod
    def with_builtin_graders(cls) -> "EvaluationEngine":
        return cls(GraderRegistry.with_builtins())

    def evaluate_test(
        self,
        test_case: ExecutableTestCase,
        actual_output: EvaluationValue,
    ) -> TestEvaluationResult:
        grader = self._registry.resolve(test_case.grader_config)
        grade = grader.grade(
            expected=test_case.expected_output,
            actual=actual_output,
            config=test_case.grader_config,
        )
        return TestEvaluationResult(test_case_id=test_case.id, grade=grade)

    def evaluate_batch(
        self,
        test_cases: Sequence[ExecutableTestCase],
        actual_outputs: Mapping[str, EvaluationValue],
    ) -> EvaluationResult:
        cases = tuple(test_cases)
        if not cases:
            raise EvaluationBatchError("Cannot evaluate an empty test collection.")

        test_ids = tuple(test_case.id for test_case in cases)
        if len(set(test_ids)) != len(test_ids):
            raise EvaluationBatchError("Evaluation test-case IDs must be unique.")

        unknown_output_ids = set(actual_outputs).difference(test_ids)
        if unknown_output_ids:
            unknown = ", ".join(sorted(unknown_output_ids))
            raise EvaluationBatchError(f"Outputs contain unknown test-case IDs: {unknown}.")

        results = tuple(
            self.evaluate_test(test_case, actual_outputs[test_case.id])
            if test_case.id in actual_outputs
            else TestEvaluationResult(
                test_case_id=test_case.id,
                grade=GradeResult(
                    passed=False,
                    failure_reason=FailureReason.MISSING_OUTPUT,
                    diagnostic=SafeDiagnostic(
                        code=FailureReason.MISSING_OUTPUT.value,
                        message="No model output was provided for this test.",
                    ),
                ),
            )
            for test_case in cases
        )
        return EvaluationResult(test_results=results)
