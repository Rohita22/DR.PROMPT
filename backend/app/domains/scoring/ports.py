from typing import Protocol


class PromptTokenCounter(Protocol):
    """Counts only player-authored prompt text with a model-compatible tokenizer."""

    def count(self, prompt: str, model_identifier: str | None = None) -> int: ...
