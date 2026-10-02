import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.exceptions import AuthenticationServiceError, PersistenceError
from app.infrastructure.auth import create_access_token_verifier
from app.infrastructure.database import create_session_factory


def test_database_configuration_is_optional_for_offline_unit_tests() -> None:
    settings = Settings(_env_file=None)

    assert settings.database_url is None
    with pytest.raises(PersistenceError, match="configuration is unavailable"):
        create_session_factory(settings)


def test_database_configuration_requires_async_postgresql_driver() -> None:
    with pytest.raises(ValidationError, match=r"postgresql\+asyncpg"):
        Settings(DATABASE_URL="postgresql://localhost/dr_prompt", _env_file=None)


def test_database_configuration_accepts_asyncpg_url() -> None:
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/dr_prompt",
        _env_file=None,
    )

    assert settings.database_url is not None
    assert settings.database_url.get_secret_value().startswith("postgresql+asyncpg://")


def test_authentication_configuration_is_optional_until_protected_route_use() -> None:
    settings = Settings(SUPABASE_URL="", _env_file=None)

    assert settings.supabase_url is None
    with pytest.raises(AuthenticationServiceError, match="configuration is unavailable"):
        create_access_token_verifier(settings)


def test_supabase_auth_configuration_accepts_public_project_url() -> None:
    settings = Settings(
        SUPABASE_URL="https://project-ref.supabase.co",
        SUPABASE_JWT_AUDIENCE="authenticated",
        _env_file=None,
    )

    assert str(settings.supabase_url).rstrip("/") == "https://project-ref.supabase.co"


def test_application_execution_guard_defaults_and_overrides_are_centralized() -> None:
    defaults = Settings(_env_file=None)
    configured = Settings(
        APPLICATION_RUN_COOLDOWN_SECONDS=3,
        APPLICATION_SUBMIT_COOLDOWN_SECONDS=9,
        APPLICATION_EXECUTION_LOCK_TIMEOUT_SECONDS=120,
        _env_file=None,
    )

    assert (
        defaults.application_run_cooldown_seconds,
        defaults.application_submit_cooldown_seconds,
        defaults.application_execution_lock_timeout_seconds,
    ) == (10, 20, 180)
    assert (
        configured.application_run_cooldown_seconds,
        configured.application_submit_cooldown_seconds,
        configured.application_execution_lock_timeout_seconds,
    ) == (3, 9, 120)
