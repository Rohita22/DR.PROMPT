"""Both packages through the same real build/browser executor with deterministic agents."""

import asyncio
import os
from dataclasses import replace

import pytest

from app.domains.execution import (
    AgentStatus,
    ChallengeExecutionRequest,
    ChangedFilesArtifact,
    ScreenshotArtifact,
)
from app.domains.execution.application import ApplicationChallengeExecutor
from app.infrastructure.application import (
    LocalWorkspaceFactory,
    PlaywrightApplicationEvaluator,
    StarterProjectRepository,
)
from app.infrastructure.challenges.application_fixtures import (
    APPLICATION_CHALLENGES,
    PRICING_GRID_CHALLENGE,
)
from tests.fakes.application import FakeCodingAgent, edit_output, solution_output, tree_digest
from tests.fakes.pricing import PRICING_STARTER, SOLUTION, pricing_output


def execute(tmp_path, output, hidden=True):
    packages = StarterProjectRepository()
    executor = ApplicationChallengeExecutor(
        FakeCodingAgent(output),
        LocalWorkspaceFactory(packages, tmp_path),
        PlaywrightApplicationEvaluator(os.getenv("APPLICATION_BROWSER_CHANNEL") or None),
        packages,
    )
    method = executor.execute_hidden if hidden else executor.execute_visible
    return asyncio.run(
        method(ChallengeExecutionRequest(PRICING_GRID_CHALLENGE, "Arrange pricing plans."))
    )


def test_two_packages_share_one_executor_and_produce_full_scores(tmp_path):
    packages = StarterProjectRepository()
    before = {p.id: tree_digest(packages.starter_dir(p.id)) for p in packages.catalog()}
    agent = FakeCodingAgent(solution_output())
    executor = ApplicationChallengeExecutor(
        agent,
        LocalWorkspaceFactory(packages, tmp_path),
        PlaywrightApplicationEvaluator(os.getenv("APPLICATION_BROWSER_CHANNEL") or None),
        packages,
    )
    for playable, output in zip(
        APPLICATION_CHALLENGES, (solution_output(), pricing_output()), strict=True
    ):
        agent.output_text = output
        request = ChallengeExecutionRequest(playable, "Follow the layout requirements.")
        visible = asyncio.run(executor.execute_visible(request))
        hidden = asyncio.run(executor.execute_hidden(request))
        assert visible.evaluation_score == hidden.evaluation_score == 100
        assert visible.total_checks == 4
        shots = [a for a in visible.artifacts if isinstance(a, ScreenshotArtifact)]
        assert [s.label for s in shots] == ["Desktop", "Phone"]
        assert all(s.png.startswith(b"\x89PNG") and len(s.png) > 5000 for s in shots)
    assert before == {p.id: tree_digest(packages.starter_dir(p.id)) for p in packages.catalog()}
    assert list(tmp_path.iterdir()) == []


def test_pricing_starter_is_partial_and_below_completion_threshold(tmp_path):
    result = execute(tmp_path, pricing_output("\n/* no layout change */"))
    failures = {c.test_case_id for c in result.check_results if not c.grade.passed}
    assert {
        "desktop_cards",
        "featured_plan",
        "mobile_no_overflow",
        "cards_stacked",
        "small_no_overflow",
    } <= failures
    assert 0 < result.evaluation_score < 70
    assert result.evaluation_score == pytest.approx(
        result.passed_checks / result.total_checks * 100
    )


def test_pricing_rejected_edit_never_builds_and_cleans_workspace(tmp_path):
    result = execute(tmp_path, edit_output(**{"build.mjs": "process.exit(0)"}))
    assert result.evaluation_score == 0
    assert (
        next(a for a in result.artifacts if isinstance(a, ChangedFilesArtifact)).agent_status
        is AgentStatus.REJECTED
    )
    assert not any(isinstance(a, ScreenshotArtifact) for a in result.artifacts)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("old", "new", "failed"),
    [
        (">Pro</h2>", ">Premium</h2>", "plan_names"),
        ("$29 / month", "$1 / month", "plan_prices"),
        ("Unlimited projects", "Limited projects", "plan_features"),
        ('href="#start-pro"', 'href="#wrong"', "action_destinations"),
        ("© 2026 Forma", "© 2027 Forma", "footer_unchanged"),
    ],
)
def test_pricing_protected_content_checks_detect_changes(tmp_path, old, new, failed):
    html = (PRICING_STARTER / "src/index.html").read_text(encoding="utf-8-sig").replace(old, new)
    css = (PRICING_STARTER / "src/styles.css").read_text(encoding="utf-8-sig") + SOLUTION
    result = execute(tmp_path, edit_output(**{"src/index.html": html, "src/styles.css": css}))
    assert not next(c for c in result.check_results if c.test_case_id == failed).grade.passed


def test_configured_screenshots_choose_labels_and_safe_subset(tmp_path):
    packages = StarterProjectRepository()
    config = PRICING_GRID_CHALLENGE.version.application_config
    config = replace(
        config,
        viewports=tuple(
            replace(v, screenshot=False)
            if v.id == "desktop"
            else replace(v, label="Pocket view")
            if v.id == "mobile"
            else v
            for v in config.viewports
        ),
    )
    playable = replace(
        PRICING_GRID_CHALLENGE,
        version=replace(PRICING_GRID_CHALLENGE.version, application_config=config),
    )
    executor = ApplicationChallengeExecutor(
        FakeCodingAgent(pricing_output()),
        LocalWorkspaceFactory(packages, tmp_path),
        PlaywrightApplicationEvaluator(os.getenv("APPLICATION_BROWSER_CHANNEL") or None),
        packages,
    )
    result = asyncio.run(
        executor.execute_visible(
            ChallengeExecutionRequest(playable, "Make the pricing responsive.")
        )
    )
    assert [
        (s.viewport, s.label) for s in result.artifacts if isinstance(s, ScreenshotArtifact)
    ] == [("mobile", "Pocket view")]
