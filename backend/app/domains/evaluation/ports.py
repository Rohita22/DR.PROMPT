from typing import Protocol, TypeVar

from app.domains.evaluation.configuration import GraderConfiguration
from app.domains.evaluation.model_execution import LLMExecutionRequest, LLMExecutionResult
from app.domains.evaluation.results import GradeResult
from app.domains.evaluation.types import EvaluationValue

GraderConfigT = TypeVar("GraderConfigT", bound=GraderConfiguration, contravariant=True)


class LLMProvider(Protocol):
    """Vendor-neutral boundary for asynchronous model execution."""

    async def generate(self, request: LLMExecutionRequest) -> LLMExecutionResult: ...


class Grader(Protocol[GraderConfigT]):
    """Domain contract implemented by deterministic grading strategies."""

    def grade(
        self,
        *,
        expected: EvaluationValue,
        actual: EvaluationValue,
        config: GraderConfigT,
    ) -> GradeResult: ...
