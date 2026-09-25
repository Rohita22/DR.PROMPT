from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite

from app.domains.evaluation.errors import EvaluationConfigurationError
from app.domains.evaluation.types import EvaluationValue


class GraderType(StrEnum):
    EXACT_MATCH = "exact_match"
    CASE_INSENSITIVE_EXACT_MATCH = "case_insensitive_exact_match"
    ALLOWED_LABEL = "allowed_label"
    JSON_SCHEMA = "json_schema"
    FIELD_COMPARISON = "field_comparison"
    ARRAY_COMPARISON = "array_comparison"


@dataclass(frozen=True, slots=True)
class ExactMatchGraderConfig:
    grader_type: GraderType = field(default=GraderType.EXACT_MATCH, init=False)


@dataclass(frozen=True, slots=True)
class CaseInsensitiveExactMatchGraderConfig:
    grader_type: GraderType = field(
        default=GraderType.CASE_INSENSITIVE_EXACT_MATCH,
        init=False,
    )


@dataclass(frozen=True, slots=True)
class AllowedLabelGraderConfig:
    allowed_labels: frozenset[str]
    grader_type: GraderType = field(default=GraderType.ALLOWED_LABEL, init=False)

    def __post_init__(self) -> None:
        normalized = frozenset(label.strip() for label in self.allowed_labels if label.strip())
        if not normalized:
            raise EvaluationConfigurationError("Allowed-label grading requires at least one label.")
        if len(normalized) != len(self.allowed_labels):
            raise EvaluationConfigurationError("Allowed labels must be non-blank and unique.")
        object.__setattr__(self, "allowed_labels", normalized)


@dataclass(frozen=True, slots=True)
class JsonSchemaGraderConfig:
    schema: Mapping[str, EvaluationValue]
    grader_type: GraderType = field(default=GraderType.JSON_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if not self.schema:
            raise EvaluationConfigurationError("JSON-schema grading requires a schema.")


@dataclass(frozen=True, slots=True)
class FieldComparisonGraderConfig:
    fields: tuple[str, ...]
    grader_type: GraderType = field(default=GraderType.FIELD_COMPARISON, init=False)

    def __post_init__(self) -> None:
        normalized = tuple(field_name.strip() for field_name in self.fields)
        if not normalized or any(not field_name for field_name in normalized):
            raise EvaluationConfigurationError("Field comparison requires non-blank field names.")
        if len(set(normalized)) != len(normalized):
            raise EvaluationConfigurationError("Field comparison fields must be unique.")
        object.__setattr__(self, "fields", normalized)


@dataclass(frozen=True, slots=True)
class ArrayComparisonGraderConfig:
    order_matters: bool = True
    grader_type: GraderType = field(default=GraderType.ARRAY_COMPARISON, init=False)


type GraderConfiguration = (
    ExactMatchGraderConfig
    | CaseInsensitiveExactMatchGraderConfig
    | AllowedLabelGraderConfig
    | JsonSchemaGraderConfig
    | FieldComparisonGraderConfig
    | ArrayComparisonGraderConfig
)


@dataclass(frozen=True, slots=True)
class EvaluationConfiguration:
    """Challenge-level default; a test case keeps its effective grader explicit."""

    default_grader: GraderConfiguration


@dataclass(frozen=True, slots=True)
class ModelConfiguration:
    model_id: str
    temperature: float
    max_output_tokens: int
    configuration_version: str
    system_wrapper: str | None = None

    def __post_init__(self) -> None:
        model_id = self.model_id.strip()
        configuration_version = self.configuration_version.strip()
        if not model_id:
            raise EvaluationConfigurationError("Model identifier cannot be blank.")
        if not configuration_version:
            raise EvaluationConfigurationError("Model configuration version cannot be blank.")
        if not isfinite(self.temperature) or not 0 <= self.temperature <= 2:
            raise EvaluationConfigurationError("Temperature must be between 0 and 2.")
        if self.max_output_tokens <= 0:
            raise EvaluationConfigurationError("Model max output tokens must be positive.")
        if self.system_wrapper is not None and not self.system_wrapper.strip():
            raise EvaluationConfigurationError("System wrapper cannot be blank when provided.")

        object.__setattr__(self, "model_id", model_id)
        object.__setattr__(self, "configuration_version", configuration_version)
        if self.system_wrapper is not None:
            object.__setattr__(self, "system_wrapper", self.system_wrapper.strip())
