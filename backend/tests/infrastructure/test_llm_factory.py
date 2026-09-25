import pytest

from app.core.config.settings import Settings
from app.core.exceptions import LLMAuthenticationError
from app.infrastructure.llm import factory
from app.infrastructure.llm.groq_provider import GroqProvider


class UnusedFakeClient:
    pass


def test_missing_api_key_fails_only_when_provider_is_constructed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    settings = Settings(_env_file=None)

    with pytest.raises(LLMAuthenticationError, match="not configured"):
        factory.create_llm_provider(settings)


def test_settings_reads_backend_only_groq_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "environment-test-key")
    monkeypatch.setenv("GROQ_TIMEOUT_SECONDS", "17.5")

    settings = Settings(_env_file=None)

    assert settings.groq_api_key is not None
    assert settings.groq_api_key.get_secret_value() == "environment-test-key"
    assert settings.groq_timeout_seconds == 17.5


def test_factory_passes_secret_timeout_and_disables_sdk_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    fake_client = UnusedFakeClient()

    def fake_async_groq(**kwargs: object) -> UnusedFakeClient:
        captured.update(kwargs)
        return fake_client

    monkeypatch.setattr(factory, "AsyncGroq", fake_async_groq)
    settings = Settings(
        _env_file=None,
        GROQ_API_KEY="test-only-api-key",
        GROQ_TIMEOUT_SECONDS=12,
    )

    provider = factory.create_llm_provider(settings)

    assert isinstance(provider, GroqProvider)
    assert captured == {
        "api_key": "test-only-api-key",
        "timeout": 12.0,
        "max_retries": 0,
    }
    assert "test-only-api-key" not in repr(settings)
