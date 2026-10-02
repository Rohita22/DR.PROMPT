import json
from pathlib import Path

from app.domains.application.models import Box, ElementMetrics, LayoutMetrics
from app.domains.application.ports import (
    AgentResult,
    AgentTask,
    ApplicationInspection,
    Workspace,
)
from app.domains.execution import BuildArtifact, BuildStatus, ScreenshotArtifact
from app.infrastructure.application.starter_projects import APPLICATION_CHALLENGES_ROOT
from app.infrastructure.challenges.application_fixtures import RESPONSIVE_HERO_CONFIG

VIEWPORTS = {v.id: (v.width, v.height) for v in RESPONSIVE_HERO_CONFIG.viewports}
SCREENSHOT_VIEWPORTS = tuple(v.id for v in RESPONSIVE_HERO_CONFIG.viewports if v.screenshot)

STARTER_ROOT = APPLICATION_CHALLENGES_ROOT / "responsive_hero" / "starter"

# A correct responsive-hero change used as deterministic fake agent output.
SOLUTION_CSS_APPENDIX = """
.hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 48px;
  align-items: center;
}

.hero-visual {
  width: 100%;
  margin-top: 0;
}

@media (max-width: 760px) {
  .hero {
    grid-template-columns: minmax(0, 1fr);
    padding: 40px 20px;
  }

  .hero h1 {
    font-size: 36px;
  }
}
"""


def starter_text(path: str) -> str:
    return (STARTER_ROOT / path).read_text(encoding="utf-8")


def solution_output() -> str:
    return json.dumps(
        {
            "files": [
                {
                    "path": "src/styles.css",
                    "content": starter_text("src/styles.css") + SOLUTION_CSS_APPENDIX,
                }
            ]
        }
    )


def edit_output(**files: str) -> str:
    return json.dumps(
        {"files": [{"path": path, "content": content} for path, content in files.items()]}
    )


class FakeCodingAgent:
    """Offline coding agent returning a fixed raw response and recording each task."""

    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.tasks: list[AgentTask] = []

    async def apply_instructions(self, task: AgentTask) -> AgentResult:
        self.tasks.append(task)
        return AgentResult(output_text=self.output_text)


def tree_digest(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


PNG = b"\x89PNG\r\n\x1a\nfake"


def layout(width: int, height: int, *, two_column: bool, overflow: bool = False) -> LayoutMetrics:
    """Synthetic measurements: two columns side by side, or content stacked above visual."""
    half = width / 2
    if two_column:
        content = Box(32, 120, half - 56, 360, True)
        visual = Box(half + 24, 120, half - 56, 360, True)
    else:
        content = Box(16, 100, width - 32, 380, True)
        visual = Box(16, 520, width - 32, 260, True)
    return LayoutMetrics(
        viewport_width=width,
        viewport_height=height,
        scroll_width=width + (400 if overflow else 0),
        elements={
            '[data-role="hero-content"]': (ElementMetrics(content),),
            '[data-role="hero-visual"]': (ElementMetrics(visual),),
            '[data-role="hero-cta"]': (
                ElementMetrics(
                    Box(content.x, content.y + 280, 180, 48, True), "a", "#signup", True
                ),
            ),
            'main [data-role="hero"]': (ElementMetrics(Box(0, 64, width, 700, True)),),
            '[data-role="hero"] h1': (ElementMetrics(content, "h1"),),
            "h1": (ElementMetrics(content, "h1"),),
            'a[data-role="hero-cta"], button[data-role="hero-cta"]': (
                ElementMetrics(content, "a"),
            ),
        },
    )


def responsive_layouts() -> dict[str, LayoutMetrics]:
    return {
        name: layout(width, height, two_column=width >= 1000)
        for name, (width, height) in VIEWPORTS.items()
    }


def starter_layouts() -> dict[str, LayoutMetrics]:
    return {
        name: layout(width, height, two_column=False, overflow=width < 600)
        for name, (width, height) in VIEWPORTS.items()
    }


class FakeEvaluator:
    """Offline evaluator returning canned measurements and recording each workspace."""

    def __init__(
        self,
        layouts: dict[str, LayoutMetrics] | None = None,
        build: BuildStatus = BuildStatus.PASSED,
    ) -> None:
        self.layouts = responsive_layouts() if layouts is None else layouts
        self.build = build
        self.roots: list[Path] = []
        self.page_sources: list[str] = []

    async def inspect(self, workspace: Workspace, config, package) -> ApplicationInspection:
        self.roots.append(workspace.root)
        self.page_sources.append(workspace.read_text(config.page_source))
        if self.build is not BuildStatus.PASSED:
            return ApplicationInspection(BuildArtifact(self.build, "build error: broken"), {}, ())
        screenshots = tuple(
            ScreenshotArtifact(name, *VIEWPORTS[name], PNG) for name in SCREENSHOT_VIEWPORTS
        )
        return ApplicationInspection(
            BuildArtifact(BuildStatus.PASSED, "Built dist/index.html and dist/styles.css."),
            self.layouts,
            screenshots,
        )
