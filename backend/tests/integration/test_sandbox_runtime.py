"""Opt-in real isolation tests. Never substitute host execution for this suite."""

import asyncio
import hashlib
import os
import sys

import pytest

from app.application.admin.package_health import ApplicationPackageHealth
from app.domains.application.sandbox import SandboxPolicy
from app.domains.execution.application import ApplicationChallengeExecutor
from app.domains.execution.models import ChallengeExecutionRequest, ScreenshotArtifact
from app.infrastructure.application import LocalWorkspaceFactory, StarterProjectRepository
from app.infrastructure.application.sandbox import RootlessDockerSandbox
from app.infrastructure.challenges.application_fixtures import EXECUTABLE_CHALLENGES
from tests.fakes.application import FakeCodingAgent
from tests.fakes.executable import executable_solution

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        sys.platform != "linux" or os.getenv("RUN_SANDBOX_TESTS") != "1",
        reason="Requires explicitly opted-in Linux rootless container runtime",
    ),
]


def runtime():
    sandbox = RootlessDockerSandbox(os.environ.get("APPLICATION_SANDBOX_IMAGE", ""))
    # Once opted in, an unavailable/incorrect runtime is a FAILURE, not a skipped test.
    assert asyncio.run(sandbox.capability()).available, "Configured runtime failed its safety probe"
    return sandbox


def test_real_isolation_controls_and_timeout():
    sandbox = runtime()
    probe = asyncio.run(sandbox._invoke({"probe": True}, SandboxPolicy()))
    assert probe == {
        "network_blocked": True,
        "secrets_absent": True,
        "host_paths_absent": True,
        "workspace_writable": True,
        "root_readonly": True,
        "non_root": True,
    }
    timed = asyncio.run(sandbox._invoke({"probe_timeout": True}, SandboxPolicy(timeout_seconds=10)))
    assert timed["category"] == "timeout"


@pytest.mark.parametrize("playable", EXECUTABLE_CHALLENGES)
@pytest.mark.parametrize("quality", ["good", "partial", "bad", "unsafe", "build_failure"])
def test_real_interactive_packages(playable, quality, tmp_path):
    sandbox = runtime()
    packages = StarterProjectRepository()
    slug = playable.challenge.slug
    starter = packages.starter_dir(slug)

    def hashes():
        return {
            p.relative_to(starter).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in starter.rglob("*")
            if p.is_file()
        }

    before = hashes()
    executor = ApplicationChallengeExecutor(
        FakeCodingAgent(executable_solution(slug, quality)),
        LocalWorkspaceFactory(packages, tmp_path),
        None,
        packages,
        sandbox,
    )
    result = asyncio.run(
        executor.execute_hidden(ChallengeExecutionRequest(playable, "Fix the behavior"))
    )
    if quality == "good":
        assert result.evaluation_score == 100
        assert len([a for a in result.artifacts if isinstance(a, ScreenshotArtifact)]) == 2
    elif quality in {"unsafe", "build_failure"}:
        assert result.evaluation_score < 20
    else:
        assert result.evaluation_score < 100
    assert hashes() == before and not list(tmp_path.iterdir())


@pytest.mark.parametrize("playable", EXECUTABLE_CHALLENGES)
def test_pristine_starter_health(playable, tmp_path):
    packages = StarterProjectRepository()
    health = ApplicationPackageHealth(
        packages, LocalWorkspaceFactory(packages, tmp_path), runtime(), None
    )
    result = asyncio.run(health.execute(playable.challenge.slug))
    assert result["available"] and result["build_succeeded"] and result["checks_initialized"]
    assert not list(tmp_path.iterdir())
