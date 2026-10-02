"""Real Node build + headless Chromium checks for the Responsive Hero prototype.

Offline (no provider or network calls). Skipped when Node.js or a Playwright-compatible
browser is unavailable; set APPLICATION_BROWSER_CHANNEL=chrome to use an installed Chrome.
"""

import asyncio
import os
import shutil
from pathlib import Path

import pytest

from app.domains.application.errors import ApplicationEnvironmentError
from app.domains.execution import (
    BuildArtifact,
    BuildStatus,
    ChallengeExecutionRequest,
    ScreenshotArtifact,
)
from app.domains.execution.application import ApplicationChallengeExecutor
from app.infrastructure.application import (
    LocalWorkspaceFactory,
    PlaywrightApplicationEvaluator,
    StarterProjectRepository,
)
from app.infrastructure.challenges.application_fixtures import RESPONSIVE_HERO_CHALLENGE
from tests.fakes.application import (
    STARTER_ROOT,
    FakeCodingAgent,
    edit_output,
    solution_output,
    starter_text,
    tree_digest,
)

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required")


def run(output: str, tmp_path: Path, hidden: bool = False):
    executor = ApplicationChallengeExecutor(
        FakeCodingAgent(output),
        LocalWorkspaceFactory(StarterProjectRepository(), temp_root=tmp_path),
        PlaywrightApplicationEvaluator(os.environ.get("APPLICATION_BROWSER_CHANNEL") or None),
        StarterProjectRepository(),
    )
    request = ChallengeExecutionRequest(RESPONSIVE_HERO_CHALLENGE, "Make the hero responsive.")
    method = executor.execute_hidden if hidden else executor.execute_visible
    try:
        return asyncio.run(method(request))
    except ApplicationEnvironmentError as error:
        if "browser" in error.message:
            pytest.skip("No Playwright-compatible browser is available.")
        raise


def build(result) -> BuildArtifact:
    return next(a for a in result.artifacts if isinstance(a, BuildArtifact))


def test_reference_solution_passes_visible_and_hidden_checks_with_screenshots(
    tmp_path: Path,
) -> None:
    before = tree_digest(STARTER_ROOT)
    visible = run(solution_output(), tmp_path)
    hidden = run(solution_output(), tmp_path, hidden=True)

    assert (visible.passed_checks, visible.total_checks) == (4, 4)
    assert (hidden.passed_checks, hidden.total_checks) == (9, 9)
    screenshots = [a for a in visible.artifacts if isinstance(a, ScreenshotArtifact)]
    assert [(s.viewport, s.width) for s in screenshots] == [("desktop", 1280), ("mobile", 390)]
    assert all(s.png.startswith(b"\x89PNG\r\n\x1a\n") and len(s.png) > 5_000 for s in screenshots)
    assert str(tmp_path) not in build(visible).log
    assert tree_digest(STARTER_ROOT) == before
    assert list(tmp_path.iterdir()) == []


def test_unchanged_layout_fails_the_real_layout_checks(tmp_path: Path) -> None:
    css = starter_text("src/styles.css") + "\n/* no layout change */\n"
    hidden = run(edit_output(**{"src/styles.css": css}), tmp_path, hidden=True)
    assert (hidden.passed_checks, hidden.total_checks) == (5, 9)


@pytest.mark.parametrize(
    ("files", "message"),
    [
        ({"src/styles.css": starter_text("src/styles.css") + "\n.hero {"}, "unbalanced braces"),
        (
            {
                "src/index.html": starter_text("src/index.html").replace(
                    "</main>", "<script>x()</script></main>"
                )
            },
            "Scripts and embedded frames",
        ),
        (
            {
                "src/styles.css": starter_text("src/styles.css")
                + "\nbody{background:url(https://x.test/a.png)}"
            },
            "external resources",
        ),
    ],
)
def test_build_failures_are_reported_as_sanitized_failed_checks(
    tmp_path: Path, files: dict[str, str], message: str
) -> None:
    result = run(edit_output(**files), tmp_path)
    assert build(result).status is BuildStatus.FAILED
    assert message in build(result).log
    assert str(tmp_path) not in build(result).log
    assert result.passed_checks == 0
    assert not any(isinstance(a, ScreenshotArtifact) for a in result.artifacts)
