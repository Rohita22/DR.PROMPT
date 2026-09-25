from functools import lru_cache

from pydantic import Field, SecretStr
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DR_PROMPT_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
