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
