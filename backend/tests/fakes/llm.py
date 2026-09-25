from app.domains.evaluation.model_execution import LLMExecutionRequest, LLMExecutionResult


class FakeLLMProvider:
    """Reusable offline provider with deterministic sequential results."""

    def __init__(self, result: LLMExecutionResult, *additional: LLMExecutionResult) -> None:
        self.result = result
        self.results = (result, *additional)
        self.requests: list[LLMExecutionRequest] = []

    async def generate(self, request: LLMExecutionRequest) -> LLMExecutionResult:
        self.requests.append(request)
        index = len(self.requests) - 1
        if len(self.results) == 1:
            return self.result
        if index >= len(self.results):
            raise AssertionError("FakeLLMProvider received more requests than configured results.")
        return self.results[index]
