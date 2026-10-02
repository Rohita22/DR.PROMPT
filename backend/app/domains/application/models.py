import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from types import MappingProxyType

from app.domains.application.errors import ApplicationConfigurationError
from app.domains.application.sandbox import ExecutionMode

_PROJECT_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def normalize_relative_path(path: str) -> str | None:
    """Return a canonical workspace-relative POSIX path, or None if it could escape."""
    if not path or path != path.strip() or "\\" in path or "\x00" in path or ":" in path:
        return None
    candidate = PurePosixPath(path)
    if candidate.is_absolute() or any(part in ("", ".", "..") for part in path.split("/")):
        return None
    return str(candidate)


@dataclass(frozen=True, slots=True)
class ApplicationLimits:
    agent_timeout_seconds: float = 90.0
    build_timeout_seconds: float = 20.0
    browser_timeout_seconds: float = 20.0
    max_file_bytes: int = 32_000
    max_files: int = 2
    max_log_chars: int = 2_000

    def __post_init__(self) -> None:
        timeouts = (
            self.agent_timeout_seconds,
            self.build_timeout_seconds,
            self.browser_timeout_seconds,
        )
        if any(not math.isfinite(value) or not 0 < value <= 180 for value in timeouts):
            raise ApplicationConfigurationError("Application timeouts must be positive.")
        if min(self.max_file_bytes, self.max_files, self.max_log_chars) <= 0:
            raise ApplicationConfigurationError("Application size limits must be positive.")
        if self.max_file_bytes > 64000 or self.max_files > 8 or self.max_log_chars > 4000:
            raise ApplicationConfigurationError("Application size limits exceed platform policy.")


@dataclass(frozen=True, slots=True)
class ApplicationViewport:
    id: str
    width: int
    height: int
    label: str
    screenshot: bool = False

    def __post_init__(self) -> None:
        if not _PROJECT_NAME.fullmatch(self.id):
            raise ApplicationConfigurationError("Invalid viewport ID.")
        if not 280 <= self.width <= 1920 or not 320 <= self.height <= 1200:
            raise ApplicationConfigurationError("Viewport dimensions exceed platform bounds.")
        if not self.label.strip() or len(self.label) > 60:
            raise ApplicationConfigurationError("Viewport label must contain 1–60 characters.")


@dataclass(frozen=True, slots=True)
class ApplicationChallengeConfig:
    """Versioned execution configuration for one APPLICATION challenge.

    The starter project is a repository-owned reference, not a stored source blob.
    Check IDs name server-side check implementations; hidden IDs are never serialized.
    """

    starter_project: str
    page_source: str
    editable_files: tuple[str, ...]
    build_command: tuple[str, ...]
    build_output: str
    visible_checks: tuple[str, ...]
    hidden_checks: tuple[str, ...]
    viewports: tuple[ApplicationViewport, ...]
    limits: ApplicationLimits = ApplicationLimits()
    schema_version: int = 1
    execution_mode: ExecutionMode = ExecutionMode.STATIC

    def __post_init__(self) -> None:
        if not _PROJECT_NAME.fullmatch(self.starter_project):
            raise ApplicationConfigurationError("Starter project must be a lowercase slug.")
        paths = (*self.editable_files, self.page_source, self.build_output)
        if any(normalize_relative_path(path) != path for path in paths):
            raise ApplicationConfigurationError("Application paths must be safe relative paths.")
        editable = tuple(self.editable_files)
        if not editable or len(set(editable)) != len(editable):
            raise ApplicationConfigurationError("Editable files must be a non-empty unique list.")
        allowed = (
            {".html", ".css"}
            if self.execution_mode == ExecutionMode.STATIC
            else {".tsx", ".ts", ".js", ".jsx", ".css"}
        )
        if any(PurePosixPath(path).suffix not in allowed for path in editable):
            raise ApplicationConfigurationError(
                "Editable file type is not permitted by this execution mode."
            )
        if self.execution_mode not in set(ExecutionMode):
            raise ApplicationConfigurationError("Unsupported execution mode.")
        if self.schema_version != 1:
            raise ApplicationConfigurationError("Unsupported application configuration schema.")
        viewports = tuple(self.viewports)
        if not 1 <= len(viewports) <= 6 or len({v.id for v in viewports}) != len(viewports):
            raise ApplicationConfigurationError("Configure 1–6 unique viewports.")
        if not 1 <= sum(v.screenshot for v in viewports) <= 4:
            raise ApplicationConfigurationError("Configure 1–4 screenshot views.")
        object.__setattr__(self, "viewports", viewports)
        if not self.build_command or any(not part.strip() for part in self.build_command):
            raise ApplicationConfigurationError("Build command must be a non-empty argument list.")
        for checks in (self.visible_checks, self.hidden_checks):
            if not checks or len(set(checks)) != len(checks):
                raise ApplicationConfigurationError("Check lists must be non-empty and unique.")
        object.__setattr__(self, "editable_files", editable)
        object.__setattr__(self, "build_command", tuple(self.build_command))
        object.__setattr__(self, "visible_checks", tuple(self.visible_checks))
        object.__setattr__(self, "hidden_checks", tuple(self.hidden_checks))


@dataclass(frozen=True, slots=True)
class SourceFile:
    path: str
    content: str


@dataclass(frozen=True, slots=True)
class Box:
    x: float
    y: float
    width: float
    height: float
    visible: bool

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height


@dataclass(frozen=True, slots=True)
class LayoutMetrics:
    """Rendered facts measured at one viewport; all check logic works from these."""

    viewport_width: int
    viewport_height: int
    scroll_width: int
    elements: Mapping[str, tuple["ElementMetrics", ...]]

    def __post_init__(self) -> None:
        object.__setattr__(self, "elements", MappingProxyType(dict(self.elements)))


@dataclass(frozen=True, slots=True)
class ElementMetrics:
    box: Box
    tag: str = "div"
    href: str | None = None
    hit: bool = False
    text: str = ""
    background: str = ""
    border_color: str = ""
    border_width: float = 0
    disabled: bool = False
