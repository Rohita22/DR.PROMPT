from pathlib import Path

import tiktoken
from tiktoken.load import load_tiktoken_bpe

from app.domains.scoring.errors import TokenizationError

_VOCABULARY_PATH = Path(__file__).parent / "assets" / "o200k_base.tiktoken"
_VOCABULARY_SHA256 = "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d"
_SUPPORTED_MODELS = frozenset({"openai/gpt-oss-20b", "openai/gpt-oss-120b"})
_O200K_PATTERN = "|".join(
    (
        r"[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}]*"
        r"[\p{Ll}\p{Lm}\p{Lo}\p{M}]+(?i:'s|'t|'re|'ve|'m|'ll|'d)?",
        r"[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}]+"
        r"[\p{Ll}\p{Lm}\p{Lo}\p{M}]*(?i:'s|'t|'re|'ve|'m|'ll|'d)?",
        r"\p{N}{1,3}",
        r" ?[^\s\p{L}\p{N}]+[\r\n/]*",
        r"\s*[\r\n]+",
        r"\s+(?!\S)",
        r"\s+",
    )
)


class GptOssPromptTokenCounter:
    """Offline counter using GPT-OSS's official o200k_harmony text vocabulary."""

    def __init__(self, vocabulary_path: Path = _VOCABULARY_PATH) -> None:
        try:
            mergeable_ranks = load_tiktoken_bpe(
                str(vocabulary_path),
                expected_hash=_VOCABULARY_SHA256,
            )
            self._encoding = tiktoken.Encoding(
                name="dr_prompt_o200k_harmony_text",
                pat_str=_O200K_PATTERN,
                mergeable_ranks=mergeable_ranks,
                special_tokens={},
            )
        except Exception:
            raise TokenizationError("The configured prompt tokenizer is unavailable.") from None

    def count(self, prompt: str, model_identifier: str | None = None) -> int:
        if model_identifier is not None and model_identifier not in _SUPPORTED_MODELS:
            raise TokenizationError("No authoritative tokenizer is configured for this model.")
        return len(self._encoding.encode_ordinary(prompt))
