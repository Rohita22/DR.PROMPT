import asyncio
import sys
from dataclasses import replace
from unittest.mock import AsyncMock

import pytest

from app.domains.application.errors import ApplicationConfigurationError
from app.domains.application.ports import ApplicationInspection
from app.domains.application.sandbox import (
    DisabledApplicationSandbox,
    ExecutionMode,
    SandboxCapability,
    SandboxCommandResult,
    SandboxPolicy,
    SandboxUnavailableError,
)
from app.domains.execution.application import ApplicationChallengeExecutor
from app.domains.execution.models import BuildArtifact, BuildStatus, ChallengeExecutionRequest
from app.infrastructure.application import (
    LocalWorkspaceFactory,
    PlaywrightApplicationEvaluator,
    StarterProjectRepository,
)
from app.infrastructure.application.sandbox import (
    RootlessDockerSandbox,
    bounded_process,
    container_arguments,
)
from app.infrastructure.challenges.application_fixtures import EXECUTABLE_CHALLENGES
from tests.fakes.application import FakeCodingAgent
from tests.fakes.executable import executable_solution


@pytest.mark.parametrize("playable", EXECUTABLE_CHALLENGES)
def test_unavailable_stops_before_agent_workspace_or_host_evaluator(playable, tmp_path):
    agent = FakeCodingAgent(executable_solution(playable.challenge.slug))
    evaluator = AsyncMock()
    executor = ApplicationChallengeExecutor(
        agent,
        LocalWorkspaceFactory(StarterProjectRepository(), tmp_path),
        evaluator,
        StarterProjectRepository(),
    )
    with pytest.raises(SandboxUnavailableError):
        asyncio.run(executor.execute_visible(ChallengeExecutionRequest(playable, "Fix it")))
    assert not agent.tasks
    evaluator.inspect.assert_not_called()
    assert not list(tmp_path.iterdir())


def test_container_policy_has_no_mount_network_privilege_or_ambient_environment():
    args = container_arguments("drprompt-" + "a" * 32, "sha256:" + "b" * 64, SandboxPolicy())
    assert "--network=none" in args and "--read-only" in args
    assert "--cap-drop=ALL" in args and "--security-opt=no-new-privileges" in args
    assert "--user=1000:1000" in args and "--pull=never" in args
    for flag in ("--pids-limit", "--cpus", "--memory", "--memory-swap", "--tmpfs"):
        assert flag in args
    for forbidden in (
        "--privileged",
        "--volume",
        "-v",
        "--mount",
        "--device",
        "--publish",
        "-p",
        "--env-file",
        "--env",
        "--ipc=host",
    ):
        assert forbidden not in args
    assert "/var/run/docker.sock" not in " ".join(args)
    assert "GROQ" not in " ".join(args) and "DATABASE" not in " ".join(args)
    assert "-i" in args and "--entrypoint=/usr/bin/env" in args


@pytest.mark.parametrize(
    "policy",
    [
        {"network": "host"},
        {"cpus": 0},
        {"memory_mb": 100000},
        {"pids": 0},
        {"timeout_seconds": 1000},
        {"runtime": "other"},
        {"commands": ["sh", "-c", "echo"]},
    ],
)
def test_resource_and_command_policy_rejects_expansion(policy):
    with pytest.raises(ApplicationConfigurationError):
        SandboxPolicy(**policy)


@pytest.mark.parametrize("image", ["latest", "node:latest", "sha256:bad", "-v /:/host"])
def test_image_must_be_immutable_local_id(image):
    with pytest.raises(SandboxUnavailableError):
        container_arguments("drprompt-" + "a" * 32, image, SandboxPolicy())


@pytest.mark.parametrize("playable", EXECUTABLE_CHALLENGES)
def test_package_config_policy_and_lockfiles(playable):
    packages = StarterProjectRepository()
    config = playable.version.application_config
    package = packages.validate(config)
    assert package.sandbox and config.execution_mode == ExecutionMode.SANDBOXED_EXECUTABLE
    assert config.build_command == ("sandbox", "build")
    for path in (
        "package.json",
        "tsconfig.json",
        "package-lock.json",
        "src/main.tsx",
        "../outside.ts",
    ):
        with pytest.raises(ApplicationConfigurationError):
            packages.validate(replace(config, editable_files=(path,)))
    with pytest.raises(ApplicationConfigurationError):
        packages.validate(replace(config, execution_mode=ExecutionMode.STATIC))


@pytest.mark.parametrize("playable", EXECUTABLE_CHALLENGES)
def test_static_browser_explicitly_rejects_executable_mode(playable):
    packages = StarterProjectRepository()
    config = playable.version.application_config
    with pytest.raises(SandboxUnavailableError):
        asyncio.run(
            PlaywrightApplicationEvaluator().inspect(None, config, packages.validate(config))
        )


@pytest.mark.parametrize("playable", EXECUTABLE_CHALLENGES)
@pytest.mark.parametrize(
    "quality", ["good", "partial", "bad", "unsafe", "build_failure", "timeout"]
)
def test_executor_sandbox_routing_scoring_and_cleanup(playable, quality, tmp_path):
    config = playable.version.application_config
    sandbox = AsyncMock()
    sandbox.capability.return_value = SandboxCapability(True)
    passed = quality == "good"
    values = {
        id: passed or (quality == "partial" and id == config.visible_checks[1])
        for id in config.visible_checks
    }
    sandbox.inspect.return_value = ApplicationInspection(
        BuildArtifact(
            BuildStatus.FAILED if quality in {"build_failure", "timeout"} else BuildStatus.PASSED,
            "",
        ),
        {},
        (),
        values,
    )
    evaluator = AsyncMock()
    agent = FakeCodingAgent(executable_solution(playable.challenge.slug, quality))
    executor = ApplicationChallengeExecutor(
        agent,
        LocalWorkspaceFactory(StarterProjectRepository(), tmp_path),
        evaluator,
        StarterProjectRepository(),
        sandbox,
    )
    result = asyncio.run(executor.execute_visible(ChallengeExecutionRequest(playable, "Fix it")))
    if quality == "good":
        assert result.evaluation_score == 100
    if quality in {"build_failure", "timeout", "unsafe"}:
        assert result.evaluation_score == 0
    if quality in {"partial", "bad"}:
        assert 0 < result.evaluation_score < 100
    assert len(agent.tasks) == 1 and not list(tmp_path.iterdir())
    evaluator.inspect.assert_not_called()
    if quality == "unsafe":
        sandbox.inspect.assert_not_called()
    else:
        assert sandbox.inspect.call_count == 1
        assert [c.id for c in sandbox.inspect.call_args.args[3]] == list(config.visible_checks)


def test_transport_bounds_and_timeout_do_not_run_challenge_source():
    result = asyncio.run(bounded_process((sys.executable, "-c", 'print("healthy")')))
    assert result.stdout.strip() == "healthy" and result.exit_code == 0
    with pytest.raises(ValueError):
        asyncio.run(bounded_process((sys.executable, "-c", 'print("x"*10000)'), limit=100))
    result = asyncio.run(
        bounded_process((sys.executable, "-c", "import time;time.sleep(5)"), timeout=0.1)
    )
    assert result.timed_out


@pytest.mark.parametrize("failure", ["timeout", "invalid_json", "exception"])
def test_container_is_removed_on_all_completion_paths(monkeypatch, failure):
    from app.infrastructure.application import sandbox as module

    calls = []

    async def fake(argv, **kwargs):
        calls.append(argv)
        if "rm" in argv:
            return SandboxCommandResult("cleanup", 0, "", "", 0)
        if failure == "exception":
            raise ValueError("too much output")
        return SandboxCommandResult(
            "runtime",
            0,
            "garbage" if failure == "invalid_json" else "",
            "",
            0,
            failure == "timeout",
        )

    monkeypatch.setattr(module, "bounded_process", fake)
    sandbox = RootlessDockerSandbox("sha256:" + "a" * 64)
    monkeypatch.setattr(sandbox, "_argv", lambda *args: args)
    if failure == "timeout":
        assert asyncio.run(sandbox._invoke({}, SandboxPolicy()))["category"] == "timeout"
    else:
        with pytest.raises(ValueError):
            asyncio.run(sandbox._invoke({}, SandboxPolicy()))
    assert calls[-1][:2] == ("rm", "-f")


def test_disabled_capability_has_no_runtime_details():
    capability = asyncio.run(DisabledApplicationSandbox().capability())
    assert not capability.available and capability.code == "sandbox_unavailable"
