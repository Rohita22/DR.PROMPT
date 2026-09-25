class FakePromptTokenCounter:
    def __init__(self, token_count: int) -> None:
        self.token_count = token_count
        self.requests: list[tuple[str, str | None]] = []

    def count(self, prompt: str, model_identifier: str | None = None) -> int:
        self.requests.append((prompt, model_identifier))
        return self.token_count
