from groq import AsyncGroq

from app.core.config.settings import Settings
from app.core.exceptions import LLMAuthenticationError
from app.domains.evaluation.ports import LLMProvider
from app.infrastructure.llm.groq_provider import GroqProvider


def create_llm_provider(settings: Settings) -> LLMProvider:
    """Construct the configured provider without global client state."""

    if settings.groq_api_key is None:
        raise LLMAuthenticationError("Groq API key is not configured.")
    api_key = settings.groq_api_key.get_secret_value().strip()
    if not api_key:
        raise LLMAuthenticationError("Groq API key is not configured.")

    client = AsyncGroq(
        api_key=api_key,
        timeout=settings.groq_timeout_seconds,
        max_retries=0,
    )
    return GroqProvider(client)
