from dataclasses import dataclass

from app.domains.evaluation.configuration import ModelConfiguration
from app.domains.evaluation.errors import EvaluationConfigurationError
from app.domains.evaluation.types import EvaluationValue


@dataclass(frozen=True, slots=True)
class LLMExecutionRequest:
    """Provider-neutral input for one player-prompt/test-input execution."""

    player_prompt: str
    test_input: EvaluationValue
    model_config: ModelConfiguration

    def __post_init__(self) -> None:
        if not self.player_prompt.strip():
            raise EvaluationConfigurationError("Player prompt cannot be blank.")


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int

    def __post_init__(self) -> None:
        if min(self.input_tokens, self.output_tokens, self.total_tokens) < 0:
            raise EvaluationConfigurationError("Token usage cannot be negative.")
        if self.total_tokens < self.input_tokens + self.output_tokens:
            raise EvaluationConfigurationError(
                "Total token usage cannot be less than input plus output usage."
            )


@dataclass(frozen=True, slots=True)
class LLMExecutionResult:
    output_text: str
    model_id: str
    usage: TokenUsage | None = None

    def __post_init__(self) -> None:
        model_id = self.model_id.strip()
        if not model_id:
            raise EvaluationConfigurationError("Executed model identifier cannot be blank.")
        object.__setattr__(self, "model_id", model_id)
