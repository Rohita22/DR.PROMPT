"""Provider-neutral executable isolation contract. No host fallback exists."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from app.domains.application.errors import (
    ApplicationConfigurationError,
    ApplicationEnvironmentError,
)

if TYPE_CHECKING:
    from app.domains.application.checks import CheckDefinition
    from app.domains.application.models import ApplicationChallengeConfig
    from app.domains.application.packages import ApplicationPackage
    from app.domains.application.ports import ApplicationInspection, Workspace


class ExecutionMode(StrEnum):
    STATIC = "static"
    SANDBOXED_EXECUTABLE = "sandboxed_executable"


class SandboxUnavailableError(ApplicationEnvironmentError):
    code = "sandbox_unavailable"

    def __init__(self):
        super().__init__("Executable challenges aren't available on this server right now.")


@dataclass(frozen=True, slots=True)
class SandboxPolicy:
    runtime: str = "react-typescript-v1"
    install_strategy: str = "prepared_image"
    commands: tuple[str, ...] = ("typecheck", "build", "browser_tests")
    generated_paths: tuple[str, ...] = ("dist",)
    network: str = "none"
    cpus: float = 1.0
    memory_mb: int = 768
    pids: int = 128
    timeout_seconds: int = 60
    workspace_mb: int = 32
    max_output_bytes: int = 4_000_000

    def __post_init__(self):
        if (
            self.runtime != "react-typescript-v1"
            or self.install_strategy != "prepared_image"
            or tuple(self.commands) != ("typecheck", "build", "browser_tests")
            or tuple(self.generated_paths) != ("dist",)
            or self.network != "none"
        ):
            raise ApplicationConfigurationError("Unapproved executable runtime policy.")
        if not (
            0.25 <= self.cpus <= 2
            and 256 <= self.memory_mb <= 1024
            and 32 <= self.pids <= 256
            and 10 <= self.timeout_seconds <= 120
            and 8 <= self.workspace_mb <= 64
            and 1024 <= self.max_output_bytes <= 8_000_000
        ):
            raise ApplicationConfigurationError("Sandbox limits exceed platform policy.")


@dataclass(frozen=True, slots=True)
class SandboxCommandResult:
    command_id: str
    exit_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    resource_limited: bool = False


@dataclass(frozen=True, slots=True)
class SandboxCapability:
    available: bool
    code: str | None = None


class ApplicationSandbox(Protocol):
    """Owns fresh environment, commands, bounded artifacts and guaranteed destruction.

    Only repository-owned command IDs are accepted via package policy. Implementations
    MUST isolate every build, test and browser command. Never run executable source on host.
    """

    async def capability(self) -> SandboxCapability: ...

    async def inspect(
        self,
        workspace: "Workspace",
        config: "ApplicationChallengeConfig",
        package: "ApplicationPackage",
        checks: tuple["CheckDefinition", ...],
    ) -> "ApplicationInspection": ...


class DisabledApplicationSandbox:
    async def capability(self) -> SandboxCapability:
        return SandboxCapability(False, "sandbox_unavailable")

    async def inspect(self, workspace, config, package, checks):
        raise SandboxUnavailableError()
