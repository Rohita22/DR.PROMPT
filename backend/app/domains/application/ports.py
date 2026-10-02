from collections.abc import Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from app.domains.application.models import (
    ApplicationChallengeConfig,
    LayoutMetrics,
    SourceFile,
)
from app.domains.application.packages import ApplicationPackage
from app.domains.evaluation.configuration import ModelConfiguration
from app.domains.evaluation.model_execution import TokenUsage
from app.domains.execution.models import BuildArtifact, ScreenshotArtifact


@dataclass(frozen=True, slots=True)
class AgentTask:
    """Everything the coding agent receives: the player's prompt and editable files only.

    The challenge objective and all checks are deliberately excluded; the player's
    instructions are the only description of the task the agent sees.
    """

    player_prompt: str
    files: tuple[SourceFile, ...]
    model_config: ModelConfiguration


@dataclass(frozen=True, slots=True)
class AgentResult:
    output_text: str
    usage: TokenUsage | None = None


class CodingAgent(Protocol):
    """Vendor-neutral boundary: returns raw text that is validated before any write."""

    async def apply_instructions(self, task: AgentTask) -> AgentResult: ...


class Workspace(Protocol):
    """A disposable copy of a starter project. Writes are confined to its root."""

    @property
    def root(self) -> Path: ...

    def read_text(self, path: str) -> str: ...

    def write_text(self, path: str, content: str) -> None: ...

    def modified_paths(self) -> frozenset[str]: ...


class WorkspaceFactory(Protocol):
    def create(
        self,
        starter_project: str,
        editable_files: tuple[str, ...],
    ) -> AbstractContextManager[Workspace]: ...


@dataclass(frozen=True, slots=True)
class ApplicationInspection:
    build: BuildArtifact
    layouts: Mapping[str, LayoutMetrics]
    screenshots: tuple[ScreenshotArtifact, ...]
    behavior_results: Mapping[str, bool] = field(default_factory=dict)


class ApplicationEvaluator(Protocol):
    """Runs the predefined build and measures the rendered page in a locked-down browser."""

    async def inspect(
        self,
        workspace: Workspace,
        config: ApplicationChallengeConfig,
        package: ApplicationPackage,
    ) -> ApplicationInspection: ...


class StarterPreviewReader(Protocol):
    def preview_png(self, starter_project: str, viewport: str) -> bytes | None: ...


class ApplicationPackageLoader(Protocol):
    def load(self, name: str) -> ApplicationPackage: ...

    def validate(self, config: ApplicationChallengeConfig) -> ApplicationPackage: ...

    def catalog(self) -> tuple[ApplicationPackage, ...]: ...
