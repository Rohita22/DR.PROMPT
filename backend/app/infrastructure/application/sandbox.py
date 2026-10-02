"""Rootless Linux container adapter. The daemon never receives a host bind mount.

Opt-in only; capability failure is fail-closed. All source is transported as data on
stdin. Nothing returned by a container is evaluated or imported by Python.
"""

import asyncio
import base64
import json
import logging
import os
import re
import shutil
import sys
import time
import uuid
from dataclasses import asdict, replace

from app.domains.application.errors import ApplicationEnvironmentError
from app.domains.application.ports import ApplicationInspection
from app.domains.application.sandbox import (
    DisabledApplicationSandbox,
    SandboxCapability,
    SandboxCommandResult,
    SandboxPolicy,
    SandboxUnavailableError,
)
from app.domains.execution.models import BuildArtifact, BuildStatus, ScreenshotArtifact


async def bounded_process(argv, *, data=b"", timeout=10, limit=8192):
    """Continuously drain pipes with a hard memory cap; never use a shell."""
    started = time.monotonic()
    process = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={
            key: value for key, value in os.environ.items() if key in {"PATH", "SYSTEMROOT", "HOME"}
        },
    )

    async def drain(stream):
        result = bytearray()
        while chunk := await stream.read(8192):
            if len(result) + len(chunk) > limit:
                raise ValueError("Sandbox output exceeds transport bounds")
            result.extend(chunk)
        return bytes(result)

    async def feed():
        try:
            process.stdin.write(data)
            await process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            process.stdin.close()

    jobs = [
        asyncio.create_task(drain(process.stdout)),
        asyncio.create_task(drain(process.stderr)),
        asyncio.create_task(feed()),
    ]
    timed_out = False
    try:
        out, err, _ = await asyncio.wait_for(asyncio.gather(*jobs), timeout)
        await asyncio.wait_for(process.wait(), 2)
    except TimeoutError:
        timed_out = True
        out = err = b""
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
        for job in jobs:
            job.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)
    return SandboxCommandResult(
        "runtime",
        process.returncode,
        out.decode("utf-8", errors="replace"),
        err.decode("utf-8", errors="replace"),
        time.monotonic() - started,
        timed_out,
        process.returncode == 137,
    )


def container_arguments(name: str, image: str, policy: SandboxPolicy) -> tuple[str, ...]:
    if not re.fullmatch(r"drprompt-[a-f0-9]{32}", name) or not re.fullmatch(
        r"sha256:[a-f0-9]{64}", image
    ):
        raise SandboxUnavailableError()
    return (
        "run",
        "--rm",
        "-i",
        "--name",
        name,
        "--pull=never",
        "--network=none",
        "--read-only",
        "--user=1000:1000",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit",
        str(policy.pids),
        "--cpus",
        str(policy.cpus),
        "--memory",
        f"{policy.memory_mb}m",
        "--memory-swap",
        f"{policy.memory_mb}m",
        "--shm-size=64m",
        "--init",
        "--tmpfs",
        f"/work:rw,noexec,nosuid,nodev,size={policy.workspace_mb}m,uid=1000,gid=1000,mode=700",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=64m,uid=1000,gid=1000,mode=700",
        "--workdir=/work",
        "--log-driver=none",
        "--entrypoint=/usr/bin/env",
        image,
        "-i",
        "PATH=/usr/local/bin:/usr/bin:/bin",
        "HOME=/tmp",
        "LANG=C.UTF-8",
        "PLAYWRIGHT_BROWSERS_PATH=/ms-playwright",
        "node",
        "/runtime/runner.mjs",
    )


class RootlessDockerSandbox:
    def __init__(self, image: str):
        self.image = image
        self.executable = shutil.which("docker")

    def _argv(self, *args):
        if not self.executable or sys.platform != "linux":
            raise SandboxUnavailableError()
        # No ambient DOCKER_HOST or context: only this user's local rootless daemon.
        return (self.executable, "--host", f"unix:///run/user/{os.getuid()}/docker.sock", *args)

    async def capability(self):
        try:
            container_arguments("drprompt-" + "0" * 32, self.image, SandboxPolicy())
            info = await bounded_process(self._argv("info", "--format", "{{json .}}"), limit=64000)
            state = json.loads(info.stdout)
            if (
                info.exit_code
                or state.get("OSType") != "linux"
                or str(state.get("CgroupVersion")) != "2"
            ):
                raise ValueError()
            if not any("rootless" in x for x in state.get("SecurityOptions", [])):
                raise ValueError()
            image = await bounded_process(self._argv("image", "inspect", self.image), limit=64000)
            metadata = json.loads(image.stdout)[0]
            if (
                image.exit_code
                or metadata.get("Config", {}).get("Labels", {}).get("drprompt.runtime")
                != "react-typescript-v1"
            ):
                raise ValueError()
            # Probe actual cgroups and Chromium startup, not merely accepted CLI flags.
            result = await self._invoke(
                {"health": True}, replace(SandboxPolicy(), timeout_seconds=15)
            )
            return SandboxCapability(
                result.get("healthy") is True,
                None if result.get("healthy") else "sandbox_unavailable",
            )
        except (OSError, ValueError, KeyError, IndexError, ApplicationEnvironmentError):
            return SandboxCapability(False, "sandbox_unavailable")

    async def _invoke(self, payload, policy):
        name = "drprompt-" + uuid.uuid4().hex
        result = None
        try:
            result = await bounded_process(
                self._argv(*container_arguments(name, self.image, policy)),
                data=json.dumps(payload).encode(),
                timeout=policy.timeout_seconds,
                limit=policy.max_output_bytes,
            )
            if result.timed_out:
                return {"build": False, "category": "timeout", "checks": {}, "screenshots": []}
            if result.resource_limited:
                return {
                    "build": False,
                    "category": "resource_limit",
                    "checks": {},
                    "screenshots": [],
                }
            if result.exit_code:
                raise SandboxUnavailableError()
            return json.loads(result.stdout)
        finally:
            # Independent of CLI cancellation or timeout; destroys all container processes.
            cleanup = await asyncio.shield(
                bounded_process(self._argv("rm", "-f", name), timeout=10)
            )
            if cleanup.exit_code and "No such container" not in cleanup.stderr:
                raise SandboxUnavailableError()
            logging.getLogger(__name__).info(
                "sandbox_execution",
                extra={
                    "total_seconds": result.duration_seconds if result else 0,
                    "exit_category": "timeout" if result and result.timed_out else "finished",
                },
            )

    async def inspect(self, workspace, config, package, checks):
        if package.sandbox is None:
            raise SandboxUnavailableError()
        files = {}
        total = 0
        for path in workspace.root.rglob("*"):
            if path.is_symlink() or path.is_junction():
                raise SandboxUnavailableError()
            if path.is_file():
                content = path.read_bytes()
                total += len(content)
                if len(content) > 256_000 or total > 1_000_000:
                    raise SandboxUnavailableError()
                files[path.relative_to(workspace.root).as_posix()] = base64.b64encode(
                    content
                ).decode()
        payload = {
            "files": files,
            "checks": [asdict(c) for c in checks if c.implementation == "interaction"],
            "viewports": [asdict(v) for v in config.viewports],
            "build_timeout": config.limits.build_timeout_seconds,
            "browser_timeout": config.limits.browser_timeout_seconds,
        }
        try:
            result = await self._invoke(payload, package.sandbox)
            if type(result.get("build")) is not bool or not isinstance(result.get("checks"), dict):
                raise ValueError()
            expected = {c.id for c in checks if c.implementation == "interaction"}
            if set(result["checks"]) - expected or any(
                type(v) is not bool for v in result["checks"].values()
            ):
                raise ValueError()
            for stage in ("typecheck", "build", "browser"):
                duration = result.get("metrics", {}).get(stage)
                if isinstance(duration, (int, float)) and 0 <= duration <= 120:
                    logging.getLogger(__name__).info(
                        "sandbox_stage", extra={"stage": stage, "duration_seconds": duration}
                    )
            screenshots = []
            views = {v.id: v for v in config.viewports if v.screenshot}
            seen = set()
            for shot in result.get("screenshots", []):
                view = views[shot["viewport"]]
                if view.id in seen:
                    raise ValueError()
                seen.add(view.id)
                png = base64.b64decode(shot["png"], validate=True)
                if len(png) > 1_000_000 or not png.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError()
                screenshots.append(
                    ScreenshotArtifact(view.id, view.width, view.height, png, view.label)
                )
            return ApplicationInspection(
                BuildArtifact(
                    BuildStatus.PASSED if result["build"] else BuildStatus.FAILED,
                    "App typechecked and built."
                    if result["build"]
                    else "App could not build or exceeded its execution limits.",
                ),
                {},
                tuple(screenshots),
                result["checks"],
            )
        except (ValueError, KeyError, TypeError):
            raise SandboxUnavailableError() from None


def configured_sandbox(settings):
    if settings.application_sandbox_backend == "docker-rootless":
        return RootlessDockerSandbox(settings.application_sandbox_image)
    return DisabledApplicationSandbox()
