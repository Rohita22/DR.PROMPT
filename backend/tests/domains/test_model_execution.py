import pytest

from app.domains.evaluation.configuration import ModelConfiguration
from app.domains.evaluation.errors import EvaluationConfigurationError
from app.domains.evaluation.model_execution import (
    LLMExecutionRequest,
    LLMExecutionResult,
    TokenUsage,
)


def model_config() -> ModelConfiguration:
    return ModelConfiguration(
        model_id="opaque-model-id",
        temperature=0,
        max_output_tokens=32,
        configuration_version="v1",
    )


def test_provider_neutral_execution_contract_is_immutable_and_explicit() -> None:
    request = LLMExecutionRequest(
        player_prompt="Return one label.",
        test_input={"request": "invoice"},
        model_config=model_config(),
    )
    result = LLMExecutionResult(
        output_text="billing",
        model_id="opaque-model-id",
        usage=TokenUsage(input_tokens=10, output_tokens=1, total_tokens=11),
    )

    assert request.player_prompt == "Return one label."
    assert request.test_input == {"request": "invoice"}
    assert result.usage == TokenUsage(10, 1, 11)


def test_execution_request_rejects_blank_player_prompt() -> None:
    with pytest.raises(EvaluationConfigurationError, match="Player prompt"):
        LLMExecutionRequest(player_prompt="  ", test_input="input", model_config=model_config())


@pytest.mark.parametrize("usage", [(-1, 0, 0), (10, 2, 11)])
def test_token_usage_rejects_invalid_counts(usage: tuple[int, int, int]) -> None:
    with pytest.raises(EvaluationConfigurationError, match="[Tt]oken"):
        TokenUsage(*usage)
