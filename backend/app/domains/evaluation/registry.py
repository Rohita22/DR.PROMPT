from dataclasses import dataclass
from typing import Protocol

from app.domains.evaluation.configuration import (
    AllowedLabelGraderConfig,
    ArrayComparisonGraderConfig,
    CaseInsensitiveExactMatchGraderConfig,
    ExactMatchGraderConfig,
    FieldComparisonGraderConfig,
    GraderConfiguration,
    GraderType,
    JsonSchemaGraderConfig,
)
from app.domains.evaluation.errors import (
    EvaluationConfigurationError,
    UnsupportedGraderError,
)
from app.domains.evaluation.graders import (
    AllowedLabelGrader,
    ArrayComparisonGrader,
    CaseInsensitiveExactMatchGrader,
    ExactMatchGrader,
    FieldComparisonGrader,
    JsonSchemaGrader,
)
from app.domains.evaluation.ports import Grader
from app.domains.evaluation.results import GradeResult
from app.domains.evaluation.types import EvaluationValue


class ResolvedGrader(Protocol):
    def grade(
        self,
        *,
        expected: EvaluationValue,
        actual: EvaluationValue,
        config: GraderConfiguration,
    ) -> GradeResult: ...


@dataclass(frozen=True, slots=True)
class _TypedGraderAdapter[ConfigT: GraderConfiguration]:
    config_type: type[ConfigT]
    grader: Grader[ConfigT]

    def grade(
        self,
        *,
        expected: EvaluationValue,
        actual: EvaluationValue,
        config: GraderConfiguration,
    ) -> GradeResult:
        if not isinstance(config, self.config_type):
            raise EvaluationConfigurationError(
                "The grader configuration type does not match the registered grader."
            )
        return self.grader.grade(expected=expected, actual=actual, config=config)


class GraderRegistry:
    """Explicit, per-instance resolver for deterministic grader implementations."""

    def __init__(self) -> None:
        self._graders: dict[GraderType, ResolvedGrader] = {}

    def register[ConfigT: GraderConfiguration](
        self,
        *,
        grader_type: GraderType,
        config_type: type[ConfigT],
        grader: Grader[ConfigT],
    ) -> None:
        if grader_type in self._graders:
            raise EvaluationConfigurationError(
                f"A grader is already registered for '{grader_type.value}'."
            )
        self._graders[grader_type] = _TypedGraderAdapter(
            config_type=config_type,
            grader=grader,
        )

    def resolve(self, config: GraderConfiguration) -> ResolvedGrader:
        try:
            return self._graders[config.grader_type]
        except KeyError as exc:
            raise UnsupportedGraderError(
                f"No grader is registered for '{config.grader_type.value}'."
            ) from exc

    @classmethod
    def with_builtins(cls) -> "GraderRegistry":
        registry = cls()
        registry.register(
            grader_type=GraderType.EXACT_MATCH,
            config_type=ExactMatchGraderConfig,
            grader=ExactMatchGrader(),
        )
        registry.register(
            grader_type=GraderType.CASE_INSENSITIVE_EXACT_MATCH,
            config_type=CaseInsensitiveExactMatchGraderConfig,
            grader=CaseInsensitiveExactMatchGrader(),
        )
        registry.register(
            grader_type=GraderType.ALLOWED_LABEL,
            config_type=AllowedLabelGraderConfig,
            grader=AllowedLabelGrader(),
        )
        registry.register(
            grader_type=GraderType.JSON_SCHEMA,
            config_type=JsonSchemaGraderConfig,
            grader=JsonSchemaGrader(),
        )
        registry.register(
            grader_type=GraderType.FIELD_COMPARISON,
            config_type=FieldComparisonGraderConfig,
            grader=FieldComparisonGrader(),
        )
        registry.register(
            grader_type=GraderType.ARRAY_COMPARISON,
            config_type=ArrayComparisonGraderConfig,
            grader=ArrayComparisonGrader(),
        )
        return registry
