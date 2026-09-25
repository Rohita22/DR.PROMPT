import socket

import pytest

from app.domains.scoring.errors import TokenizationError
from app.infrastructure.tokenization import GptOssPromptTokenCounter


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("", 0),
        ("hello", 1),
        ("Hello, world!", 4),
        ("Return exactly YES or NO.", 6),
        ("line one\nline two", 5),
        ("   ", 1),
    ],
)
def test_counts_known_gpt_oss_o200k_harmony_examples(
    prompt: str,
    expected: int,
) -> None:
    counter = GptOssPromptTokenCounter()

    assert counter.count(prompt, "openai/gpt-oss-20b") == expected
    assert counter.count(prompt, "openai/gpt-oss-20b") == expected


def test_tokenization_uses_only_local_assets(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_network(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("Token counting attempted network access.")

    monkeypatch.setattr(socket, "create_connection", fail_network)

    counter = GptOssPromptTokenCounter()

    assert counter.count("Offline prompt counting.", "openai/gpt-oss-20b") > 0


def test_rejects_models_without_an_authoritative_configured_tokenizer() -> None:
    counter = GptOssPromptTokenCounter()

    with pytest.raises(TokenizationError, match="authoritative tokenizer"):
        counter.count("Prompt", "another-provider/model")
