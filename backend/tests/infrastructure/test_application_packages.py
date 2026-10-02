"""Package policy rejects unsafe persisted and authoring data before model execution."""

import asyncio
import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.domains.application.checks import (
    ApplicationCheckRegistry,
    CheckDefinition,
    CheckParameters,
)
from app.domains.application.errors import (
    ApplicationConfigurationError,
    ApplicationEnvironmentError,
)
from app.domains.execution import ChallengeExecutionRequest
from app.domains.execution.application import ApplicationChallengeExecutor
from app.infrastructure.application import LocalWorkspaceFactory, StarterProjectRepository
from app.infrastructure.application.configuration import config_from_data, config_to_data
from app.infrastructure.challenges.application_fixtures import (
    RESPONSIVE_HERO_CHALLENGE,
    RESPONSIVE_HERO_CONFIG,
)
from tests.fakes.application import FakeCodingAgent, FakeEvaluator, solution_output


@pytest.mark.parametrize("name", ["responsive-hero", "pricing-grid"])
def test_package_resolves_valid_policy_and_starter(name):
    packages = StarterProjectRepository()
    package = packages.load(name)
    packages.validate(package.defaults)
    assert package.id == name
    assert packages.starter_dir(name).is_dir()
    assert package.defaults.build_command == ("node", "build.mjs")
    assert set(package.defaults.editable_files) == {"src/index.html", "src/styles.css"}
    assert config_from_data(config_to_data(package.defaults)) == package.defaults


@pytest.mark.parametrize(
    "name",
    [
        "unknown",
        "../responsive_hero",
        "/tmp",
        "C:/Windows",
        "responsive_hero",
        "x/../responsive-hero",
    ],
)
def test_package_reference_is_a_registry_key_not_a_path(name):
    with pytest.raises(ApplicationEnvironmentError):
        StarterProjectRepository().load(name)


@pytest.mark.parametrize(
    "changes",
    [
        {"editable_files": ("src/styles.css", "src/extra.css")},
        {"build_command": ("node", "-e", "process.exit(0)")},
        {"page_source": "src/other.html"},
        {"visible_checks": ("semantic_structure",)},
        {"hidden_checks": ("unknown",)},
    ],
)
def test_invalid_policy_fails_before_provider_or_workspace(tmp_path, changes):
    agent = FakeCodingAgent(solution_output())
    packages = StarterProjectRepository()
    executor = ApplicationChallengeExecutor(
        agent, LocalWorkspaceFactory(packages, tmp_path), FakeEvaluator(), packages
    )
    config = replace(RESPONSIVE_HERO_CONFIG, **changes)
    challenge = replace(
        RESPONSIVE_HERO_CHALLENGE,
        version=replace(RESPONSIVE_HERO_CHALLENGE.version, application_config=config),
    )
    with pytest.raises(ApplicationConfigurationError):
        asyncio.run(executor.execute_visible(ChallengeExecutionRequest(challenge, "Prompt")))
    assert agent.tasks == [] and list(tmp_path.iterdir()) == []


def test_file_permissions_can_be_narrowed_to_css_only(tmp_path):
    packages = StarterProjectRepository()
    config = replace(RESPONSIVE_HERO_CONFIG, editable_files=("src/styles.css",))
    packages.validate(config)
    challenge = replace(
        RESPONSIVE_HERO_CHALLENGE,
        version=replace(RESPONSIVE_HERO_CHALLENGE.version, application_config=config),
    )
    agent = FakeCodingAgent(solution_output())
    executor = ApplicationChallengeExecutor(
        agent, LocalWorkspaceFactory(packages, tmp_path), FakeEvaluator(), packages
    )
    assert (
        asyncio.run(
            executor.execute_visible(ChallengeExecutionRequest(challenge, "Prompt"))
        ).evaluation_score
        == 100
    )
    assert [f.path for f in agent.tasks[0].files] == ["src/styles.css"]


@pytest.mark.parametrize(
    "changes", [{"width": 200}, {"height": 10000}, {"id": "../escape"}, {"label": ""}]
)
def test_invalid_viewport_rejected(changes):
    with pytest.raises(ApplicationConfigurationError):
        replace(RESPONSIVE_HERO_CONFIG.viewports[0], **changes)


def test_private_view_cannot_be_published_as_screenshot():
    config = replace(
        RESPONSIVE_HERO_CONFIG,
        viewports=tuple(
            replace(v, screenshot=True) if v.id == "wide" else v
            for v in RESPONSIVE_HERO_CONFIG.viewports
        ),
    )
    with pytest.raises(ApplicationConfigurationError):
        StarterProjectRepository().validate(config)


def test_jsonb_is_strictly_revalidated():
    original = config_to_data(RESPONSIVE_HERO_CONFIG)
    for data in [
        {**original, "schema_version": 999},
        {**original, "extra": "source"},
        {**original, "limits": {"max_files": "2"}},
        {**original, "editable_files": ["build.mjs"]},
    ]:
        with pytest.raises(ApplicationConfigurationError):
            config_from_data(data)


def test_registry_instances_have_immutable_independent_implementations():
    first, second = ApplicationCheckRegistry(), ApplicationCheckRegistry()
    assert first.ids == second.ids
    with pytest.raises(TypeError):
        first._checks["bad"] = lambda f, p: True
    for check in [
        CheckDefinition("x", "eval", "Bad"),
        CheckDefinition("x", "horizontal_row", "Row"),
        CheckDefinition(
            "x",
            "element_prominent",
            "Prominent",
            CheckParameters(viewports=("desktop",), selectors=("a",), count=3),
        ),
    ]:
        with pytest.raises(ApplicationConfigurationError):
            first.validate(check)
    with pytest.raises(ApplicationConfigurationError):
        CheckParameters(tolerance=float("nan"))


def test_package_root_and_manifest_links_fail_closed(tmp_path, monkeypatch):
    packages = StarterProjectRepository()
    real = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda p: p.name == "manifest.json" or real(p))
    with pytest.raises(ApplicationEnvironmentError, match="links"):
        packages.load("responsive-hero")


def test_unknown_manifest_check_is_rejected(tmp_path):
    import shutil

    source = StarterProjectRepository().starter_dir("responsive-hero").parent
    shutil.copytree(source, tmp_path / "custom")
    path = tmp_path / "custom" / "manifest.json"
    data = json.loads(path.read_text())
    data["checks"][0]["implementation"] = "arbitrary_python"
    path.write_text(json.dumps(data))
    with pytest.raises(ApplicationConfigurationError):
        StarterProjectRepository(tmp_path, {"responsive-hero": "custom"}).load("responsive-hero")
