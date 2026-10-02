import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.domains.application.errors import ApplicationEnvironmentError

# Only what the OS loader needs; no credentials or application configuration.
_INHERITED_VARIABLES = ("SYSTEMROOT",)
_WINDOWS_PATH = re.compile(r"[A-Za-z]:[\\/][^\s'\"<>|]*")
_POSIX_PATH = re.compile(r"(?<![\w.:/])/(?:[\w.~-]+/)+[\w.~-]*")


@dataclass(frozen=True, slots=True)
class ProcessResult:
    exit_code: int | None
    output: str
    timed_out: bool


def minimal_environment(executable: Path) -> dict[str, str]:
    environment = {"PATH": str(executable.parent), "NO_COLOR": "1"}
    for name in _INHERITED_VARIABLES:
        value = os.environ.get(name)
        if value:
            environment[name] = value
    return environment


def run_predefined_command(argv: tuple[str, ...], cwd: Path, timeout: float) -> ProcessResult:
    """Run a challenge-configured argument list. Never a shell, never player-controlled."""
    located = shutil.which(argv[0])
    if located is None:
        raise ApplicationEnvironmentError("The build toolchain is unavailable.")
    executable = Path(located)
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv from trusted challenge config
            [str(executable), *argv[1:]],
            cwd=cwd,
            env=minimal_environment(executable),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ProcessResult(exit_code=None, output="", timed_out=True)
    return ProcessResult(completed.returncode, completed.stdout + completed.stderr, False)


def sanitize_log(text: str, workspace_root: Path, limit: int) -> str:
    """Strip workspace and other absolute paths, then bound the size."""
    for root in {str(workspace_root), workspace_root.as_posix()}:
        text = text.replace(root, "<project>")
    text = _WINDOWS_PATH.sub("<path>", text)
    text = _POSIX_PATH.sub("<path>", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
