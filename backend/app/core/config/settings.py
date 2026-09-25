from functools import lru_cache

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "DR. PROMPT API"
    api_v1_prefix: str = "/api/v1"
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:3000"]
    groq_api_key: SecretStr | None = Field(default=None, validation_alias="GROQ_API_KEY")
    groq_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        validation_alias="GROQ_TIMEOUT_SECONDS",
    )
    database_url: SecretStr | None = Field(default=None, validation_alias="DATABASE_URL")
    supabase_url: AnyHttpUrl | None = Field(default=None, validation_alias="SUPABASE_URL")
    supabase_jwt_audience: str = Field(
        default="authenticated",
        min_length=1,
        validation_alias="SUPABASE_JWT_AUDIENCE",
    )
    supabase_jwks_cache_seconds: int = Field(
        default=600,
        ge=0,
        validation_alias="SUPABASE_JWKS_CACHE_SECONDS",
    )
    supabase_jwks_timeout_seconds: float = Field(
        default=5.0,
        gt=0,
        validation_alias="SUPABASE_JWKS_TIMEOUT_SECONDS",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, value: object) -> object:
        if value in (None, ""):
            return None
        raw = str(value)
        if not raw.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use the postgresql+asyncpg driver.")
        return value

    @field_validator("supabase_url", mode="before")
    @classmethod
    def empty_supabase_url_is_unconfigured(cls, value: object) -> object:
        return None if value in (None, "") else value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DR_PROMPT_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
