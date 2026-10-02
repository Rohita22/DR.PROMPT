"""Render the committed starter-preview screenshots for an application challenge.

    uv run python -m app.infrastructure.application.render_starter_preview responsive-hero

Uses the same build and locked-down browser as evaluation, on an unmodified starter copy.
"""

import asyncio
import sys

from app.core.config.settings import get_settings
from app.infrastructure.application.playwright_evaluator import PlaywrightApplicationEvaluator
from app.infrastructure.application.starter_projects import (
    APPLICATION_CHALLENGES_ROOT,
    StarterProjectRepository,
)
from app.infrastructure.application.workspace import LocalWorkspaceFactory


async def render(project: str) -> None:
    package = StarterProjectRepository().load(project)
    config = package.defaults
    evaluator = PlaywrightApplicationEvaluator(get_settings().application_browser_channel)
    factory = LocalWorkspaceFactory(StarterProjectRepository())
    with factory.create(project, config.editable_files) as workspace:
        inspection = await evaluator.inspect(workspace, config, package)
    output = APPLICATION_CHALLENGES_ROOT / project.replace("-", "_") / "preview"
    output.mkdir(exist_ok=True)
    for screenshot in inspection.screenshots:
        (output / f"{screenshot.viewport}.png").write_bytes(screenshot.png)
        print(f"wrote preview/{screenshot.viewport}.png")


if __name__ == "__main__":
    asyncio.run(render(sys.argv[1] if len(sys.argv) > 1 else "responsive-hero"))
