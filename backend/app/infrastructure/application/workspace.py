import os
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from app.domains.application.errors import ApplicationEnvironmentError, WorkspacePathError
from app.domains.application.models import normalize_relative_path
from app.infrastructure.application.starter_projects import StarterProjectRepository


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _reject_links(root: Path) -> None:
    for current, directories, files in os.walk(root):
        for name in (*directories, *files):
            if (Path(current) / name).is_symlink():
                raise ApplicationEnvironmentError("Starter projects may not contain links.")


class LocalWorkspace:
    """A disposable starter copy. Only existing allowlisted files can be replaced."""

    def __init__(self, root: Path, starter: Path, editable_files: frozenset[str]) -> None:
        self._root = root
        self._starter = starter
        self._editable = editable_files

    @property
    def root(self) -> Path:
        return self._root

    def _resolve(self, path: str) -> Path:
        normalized = normalize_relative_path(path)
        if normalized is None or normalized != path:
            raise WorkspacePathError("Path is not a safe workspace-relative path.")
        current = self._root
        for part in PurePosixPath(normalized).parts:
            current = current / part
            if current.is_symlink():
                raise WorkspacePathError("Workspace paths may not traverse links.")
        if not current.resolve().is_relative_to(self._root):
            raise WorkspacePathError("Path escapes the workspace.")
        return current

    def read_text(self, path: str) -> str:
        return self._resolve(path).read_text(encoding="utf-8")

    def write_text(self, path: str, content: str) -> None:
        if path not in self._editable:
            raise WorkspacePathError(f"{path} is not an editable file.")
        target = self._resolve(path)
        if not target.is_file():
            raise WorkspacePathError(f"{path} does not exist in the starter project.")
        target.write_text(content, encoding="utf-8", newline="\n")

    def modified_paths(self) -> frozenset[str]:
        before, after = _files(self._starter), _files(self._root)
        return frozenset(
            path for path in before.keys() | after.keys() if before.get(path) != after.get(path)
        )


class LocalWorkspaceFactory:
    """Copies the canonical starter into a fresh OS temp directory and always deletes it."""

    def __init__(self, starters: StarterProjectRepository, temp_root: Path | None = None) -> None:
        self._starters = starters
        self._temp_root = temp_root

    @contextmanager
    def create(
        self,
        starter_project: str,
        editable_files: tuple[str, ...],
    ) -> Iterator[LocalWorkspace]:
        source = self._starters.starter_dir(starter_project)
        _reject_links(source)
        temporary = Path(tempfile.mkdtemp(prefix="drprompt-app-", dir=self._temp_root)).resolve()
        try:
            project = temporary / "project"
            shutil.copytree(source, project)
            yield LocalWorkspace(project, source, frozenset(editable_files))
        finally:
            shutil.rmtree(temporary, ignore_errors=True)
