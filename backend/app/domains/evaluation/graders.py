import json
from collections.abc import Mapping, Sequence
from typing import Never, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from app.domains.evaluation.configuration import (
    AllowedLabelGraderConfig,
    ArrayComparisonGraderConfig,
    CaseInsensitiveExactMatchGraderConfig,
    ExactMatchGraderConfig,
    FieldComparisonGraderConfig,
    JsonSchemaGraderConfig,
)
from app.domains.evaluation.errors import EvaluationConfigurationError
from app.domains.evaluation.results import FailureReason, GradeResult, SafeDiagnostic
from app.domains.evaluation.types import EvaluationValue


def _failure(reason: FailureReason, message: str) -> GradeResult:
    return GradeResult(
        passed=False,
        failure_reason=reason,
        diagnostic=SafeDiagnostic(code=reason.value, message=message),
    )


def _reject_non_standard_json_constant(value: str) -> Never:
    raise ValueError(f"Non-standard JSON constant: {value}")


def _parse_json(text: str) -> EvaluationValue:
    parsed: object = json.loads(text, parse_constant=_reject_non_standard_json_constant)
    return cast(EvaluationValue, parsed)


def _structured_actual(
    actual: EvaluationValue,
) -> tuple[EvaluationValue | None, GradeResult | None]:
    if not isinstance(actual, str):
        return actual, None
    try:
        return _parse_json(actual), None
    except (json.JSONDecodeError, ValueError, TypeError):
        return None, _failure(
            FailureReason.INVALID_JSON,
            "The output was not valid JSON.",
        )


class ExactMatchGrader:
    """Pure reference grader for exact, case-sensitive equality."""

    def grade(
        self,
        *,
        expected: EvaluationValue,
        actual: EvaluationValue,
        config: ExactMatchGraderConfig,
    ) -> GradeResult:
        del config
        if actual == expected:
            return GradeResult(passed=True)
        return _failure(
            FailureReason.OUTPUT_MISMATCH,
            "The output did not exactly match the expected value.",
        )


class CaseInsensitiveExactMatchGrader:
    """Strict text equality with case folding and no other normalization."""

    def grade(
        self,
        *,
        expected: EvaluationValue,
        actual: EvaluationValue,
        config: CaseInsensitiveExactMatchGraderConfig,
    ) -> GradeResult:
        del config
        if (
            isinstance(expected, str)
            and isinstance(actual, str)
            and expected.casefold() == actual.casefold()
        ):
            return GradeResult(passed=True)
        return _failure(
            FailureReason.OUTPUT_MISMATCH,
            "The output did not match the expected text when compared without case.",
        )


class AllowedLabelGrader:
    """Validates strict membership in the configured, case-sensitive label set."""

    def grade(
        self,
        *,
        expected: EvaluationValue,
        actual: EvaluationValue,
        config: AllowedLabelGraderConfig,
    ) -> GradeResult:
        del expected
        if isinstance(actual, str) and actual in config.allowed_labels:
            return GradeResult(passed=True)
        return _failure(
            FailureReason.INVALID_LABEL,
            "The output was not an allowed label.",
        )


class JsonSchemaGrader:
    """Parses model text as JSON and validates it with JSON Schema 2020-12."""

    def grade(
        self,
        *,
        expected: EvaluationValue,
        actual: EvaluationValue,
        config: JsonSchemaGraderConfig,
    ) -> GradeResult:
        del expected
        if not isinstance(actual, str):
            return _failure(
                FailureReason.INVALID_JSON,
                "The output was not JSON text.",
            )
        try:
            parsed = _parse_json(actual)
        except (json.JSONDecodeError, ValueError, TypeError):
            return _failure(
                FailureReason.INVALID_JSON,
                "The output was not valid JSON.",
            )

        try:
            Draft202012Validator.check_schema(config.schema)
            Draft202012Validator(config.schema).validate(parsed)
        except SchemaError as exc:
            raise EvaluationConfigurationError("The configured JSON schema is invalid.") from exc
        except ValidationError:
            return _failure(
                FailureReason.SCHEMA_VALIDATION_FAILED,
                "The JSON output did not satisfy the required schema.",
            )
        return GradeResult(passed=True)


class FieldComparisonGrader:
    """Compares only configured top-level fields in structured values."""

    def grade(
        self,
        *,
        expected: EvaluationValue,
        actual: EvaluationValue,
        config: FieldComparisonGraderConfig,
    ) -> GradeResult:
        if not isinstance(expected, Mapping):
            raise EvaluationConfigurationError(
                "Field comparison requires an object as the expected value."
            )

        parsed_actual, parse_failure = _structured_actual(actual)
        if parse_failure is not None:
            return parse_failure
        if not isinstance(parsed_actual, Mapping):
            return _failure(
                FailureReason.INVALID_OUTPUT,
                "The output must be a JSON object for field comparison.",
            )

        for field_name in config.fields:
            if field_name not in expected:
                raise EvaluationConfigurationError(
                    "A configured comparison field is absent from the expected value."
                )
            if field_name not in parsed_actual:
                return _failure(
                    FailureReason.MISSING_REQUIRED_FIELD,
                    "The output was missing a required field.",
                )
            if parsed_actual[field_name] != expected[field_name]:
                return _failure(
                    FailureReason.FIELD_MISMATCH,
                    "A required field did not match the expected value.",
                )
        return GradeResult(passed=True)


def _is_array(value: EvaluationValue) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _unordered_arrays_equal(
    expected: Sequence[EvaluationValue],
    actual: Sequence[EvaluationValue],
) -> bool:
    if len(expected) != len(actual):
        return False
    remaining = list(actual)
    for expected_item in expected:
        for index, actual_item in enumerate(remaining):
            if actual_item == expected_item:
                remaining.pop(index)
                break
        else:
            return False
    return not remaining


class ArrayComparisonGrader:
    """Compares arrays in ordered or count-aware unordered mode."""

    def grade(
        self,
        *,
        expected: EvaluationValue,
        actual: EvaluationValue,
        config: ArrayComparisonGraderConfig,
    ) -> GradeResult:
        if not _is_array(expected):
            raise EvaluationConfigurationError(
                "Array comparison requires an array as the expected value."
            )

        parsed_actual, parse_failure = _structured_actual(actual)
        if parse_failure is not None:
            return parse_failure
        if parsed_actual is None or not _is_array(parsed_actual):
            return _failure(
                FailureReason.EXPECTED_ARRAY,
                "The output must be a JSON array.",
            )

        expected_array = cast(Sequence[EvaluationValue], expected)
        actual_array = cast(Sequence[EvaluationValue], parsed_actual)
        matches = (
            list(expected_array) == list(actual_array)
            if config.order_matters
            else _unordered_arrays_equal(expected_array, actual_array)
        )
        if matches:
            return GradeResult(passed=True)
        return _failure(
            FailureReason.ARRAY_MISMATCH,
            "The array output did not satisfy the configured comparison.",
        )
