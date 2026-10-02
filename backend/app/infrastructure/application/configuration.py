"""Strict JSON boundary shared by persisted config and trusted manifests."""

from collections.abc import Mapping
from dataclasses import asdict
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.domains.application.errors import ApplicationConfigurationError
from app.domains.application.models import (
    ApplicationChallengeConfig,
    ApplicationLimits,
    ApplicationViewport,
)
from app.domains.application.sandbox import ExecutionMode


class LimitsData(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    agent_timeout_seconds: float = 90
    build_timeout_seconds: float = 20
    browser_timeout_seconds: float = 20
    max_file_bytes: int = 32000
    max_files: int = 2
    max_log_chars: int = 2000


class ViewportData(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    width: int
    height: int
    label: str
    screenshot: bool = False


class ApplicationConfigData(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: int
    execution_mode: Literal["static", "sandboxed_executable"] = "static"
    starter_project: str
    page_source: str
    editable_files: list[str] = Field(min_length=1, max_length=8)
    build_command: list[str]
    build_output: str
    visible_checks: list[str] = Field(min_length=1, max_length=30)
    hidden_checks: list[str] = Field(min_length=1, max_length=30)
    viewports: list[ViewportData] = Field(min_length=1, max_length=6)
    limits: LimitsData

    def to_domain(self) -> ApplicationChallengeConfig:
        return ApplicationChallengeConfig(
            schema_version=self.schema_version,
            execution_mode=ExecutionMode(self.execution_mode),
            starter_project=self.starter_project,
            page_source=self.page_source,
            editable_files=tuple(self.editable_files),
            build_command=tuple(self.build_command),
            build_output=self.build_output,
            visible_checks=tuple(self.visible_checks),
            hidden_checks=tuple(self.hidden_checks),
            viewports=tuple(ApplicationViewport(**v.model_dump()) for v in self.viewports),
            limits=ApplicationLimits(**self.limits.model_dump()),
        )


def config_from_data(data: Mapping[str, object]) -> ApplicationChallengeConfig:
    try:
        return ApplicationConfigData.model_validate(dict(data)).to_domain()
    except (ValidationError, TypeError, KeyError, ValueError):
        raise ApplicationConfigurationError("Invalid application configuration data.") from None


def config_to_data(config: ApplicationChallengeConfig) -> dict[str, object]:
    # JSON-compatible tuples must become arrays before strict boundary validation.
    import json

    return json.loads(json.dumps(asdict(config)))
