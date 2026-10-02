import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from app.domains.application.errors import ApplicationEnvironmentError, WorkspacePathError
from app.infrastructure.application.process import (
    minimal_environment,
    run_predefined_command,
    sanitize_log,
)
from app.infrastructure.application.starter_projects import StarterProjectRepository
from app.infrastructure.application.workspace import LocalWorkspaceFactory
from tests.fakes.application import STARTER_ROOT, tree_digest

EDITABLE = ("src/index.html", "src/styles.css")
SECRETS = {
    "GROQ_API_KEY": "gsk-secret-value",
    "DATABASE_URL": "postgresql+asyncpg://user:pw@db/prod",
    "ADMIN_API_KEY": "admin-secret-value",
    "SUPABASE_URL": "https://secret.supabase.co",
}
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required")


def factory(tmp_path: Path) -> LocalWorkspaceFactory:
    return LocalWorkspaceFactory(StarterProjectRepository(), temp_root=tmp_path)


def test_each_workspace_is_a_fresh_copy_and_the_canonical_starter_never_changes(
    tmp_path: Path,
) -> None:
    before = tree_digest(STARTER_ROOT)
    workspaces = factory(tmp_path)
    with workspaces.create("responsive-hero", EDITABLE) as first:
        first_root = first.root
        first.write_text("src/styles.css", "body { color: red; }")
        assert first.modified_paths() == {"src/styles.css"}
    with workspaces.create("responsive-hero", EDITABLE) as second:
        assert second.root != first_root
        assert second.read_text("src/styles.css") == (STARTER_ROOT / "src/styles.css").read_text(
            encoding="utf-8"
        )
        assert second.modified_paths() == frozenset()
    assert tree_digest(STARTER_ROOT) == before


def test_workspace_is_deleted_after_use_even_when_execution_fails(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError), factory(tmp_path).create("responsive-hero", EDITABLE) as ws:
        root = ws.root
        raise RuntimeError("boom")
    assert not root.exists()
    assert list(tmp_path.iterdir()) == []


def test_workspace_contains_only_starter_files_and_no_environment_files(tmp_path: Path) -> None:
    with factory(tmp_path).create("responsive-hero", EDITABLE) as ws:
        files = set(tree_digest(ws.root))
        assert files == set(tree_digest(STARTER_ROOT))
        assert not any(name.endswith(".env") or ".env." in name for name in files)
        assert ws.root.resolve().is_relative_to(tmp_path.resolve())
        backend_root = Path(__file__).resolve().parents[2]
        assert not ws.root.resolve().is_relative_to(backend_root)


@pytest.mark.parametrize(
    "path",
    [
        "../escape.css",
        "src/../../escape.css",
        "/etc/passwd",
        "C:/Windows/win.ini",
        "src\\styles.css",
    ],
)
def test_workspace_rejects_traversal_and_absolute_writes(tmp_path: Path, path: str) -> None:
    with factory(tmp_path).create("responsive-hero", EDITABLE) as ws:
        with pytest.raises(WorkspacePathError):
            ws.write_text(path, "x")
        with pytest.raises(WorkspacePathError):
            ws.read_text(path)


def test_workspace_rejects_non_editable_and_new_files(tmp_path: Path) -> None:
    with factory(tmp_path).create("responsive-hero", EDITABLE) as ws:
        for path in ("build.mjs", "src/new.css", "dist/index.html"):
            with pytest.raises(WorkspacePathError):
                ws.write_text(path, "x")
    editable = (*EDITABLE, "src/missing.css")
    with (
        factory(tmp_path).create("responsive-hero", editable) as ws,
        pytest.raises(WorkspacePathError, match="does not exist"),
    ):
        ws.write_text("src/missing.css", "x")


def test_workspace_refuses_to_write_through_a_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path / "outside.css"
    outside.write_text("original", encoding="utf-8")
    with factory(tmp_path).create("responsive-hero", EDITABLE) as ws:
        target = ws.root / "src" / "styles.css"
        target.unlink()
        try:
            target.symlink_to(outside)
        except OSError:
            pytest.skip("Symlink creation is not permitted on this machine.")
        with pytest.raises(WorkspacePathError):
            ws.write_text("src/styles.css", "hijacked")
    assert outside.read_text(encoding="utf-8") == "original"


def test_starter_projects_containing_links_are_refused(tmp_path: Path) -> None:
    project = tmp_path / "root" / "linked"
    shutil.copytree(STARTER_ROOT, project / "starter")
    try:
        (project / "starter" / "leak").symlink_to(tmp_path)
    except OSError:
        pytest.skip("Symlink creation is not permitted on this machine.")
    workspaces = LocalWorkspaceFactory(StarterProjectRepository(tmp_path / "root"), tmp_path)
    with pytest.raises(ApplicationEnvironmentError), workspaces.create("linked", EDITABLE):
        pass


@pytest.mark.parametrize(
    "name", ["../responsive_hero", "Responsive-Hero", "responsive_hero", "x/y"]
)
def test_starter_repository_rejects_unsafe_or_unknown_references(name: str) -> None:
    with pytest.raises(ApplicationEnvironmentError):
        StarterProjectRepository().starter_dir(name)


def test_starter_preview_lookup_is_limited_to_known_viewports() -> None:
    repository = StarterProjectRepository()
    assert repository.preview_png("responsive-hero", "desktop").startswith(b"\x89PNG")
    assert repository.preview_png("responsive-hero", "../../.env") is None
    assert repository.preview_png("responsive-hero", "wide") is None


def test_build_environment_excludes_every_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in SECRETS.items():
        monkeypatch.setenv(key, value)
    environment = minimal_environment(Path(sys.executable))
    assert set(environment) <= {"PATH", "NO_COLOR", "SYSTEMROOT"}
    assert not set(SECRETS.values()) & set(environment.values())


@requires_node
def test_real_child_process_sees_no_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key, value in SECRETS.items():
        monkeypatch.setenv(key, value)
    result = run_predefined_command(
        ("node", "-e", "process.stdout.write(JSON.stringify(process.env))"), tmp_path, 20
    )
    assert result.exit_code == 0
    child_environment = json.loads(result.output)
    assert not set(SECRETS) & set(child_environment)
    assert not set(SECRETS.values()) & set(child_environment.values())


@requires_node
def test_predefined_commands_are_killed_at_their_timeout(tmp_path: Path) -> None:
    result = run_predefined_command(("node", "-e", "setTimeout(() => {}, 20000)"), tmp_path, 0.5)
    assert result.timed_out
    assert result.exit_code is None


def test_missing_toolchain_is_an_environment_error(tmp_path: Path) -> None:
    with pytest.raises(ApplicationEnvironmentError):
        run_predefined_command(("definitely-not-a-real-binary-xyz",), tmp_path, 1)


def test_logs_are_stripped_of_paths_and_truncated(tmp_path: Path) -> None:
    root = tmp_path / "project"
    text = (
        f"error in {root}{os.sep}src{os.sep}styles.css\n"
        "at C:\\Users\\someone\\secret\\file.js and /home/app/.env\n"
        "build error: styles.css has unbalanced braces."
    )
    cleaned = sanitize_log(text, root, 500)
    assert str(tmp_path) not in cleaned
    assert "someone" not in cleaned and "/home/app" not in cleaned
    assert "styles.css has unbalanced braces." in cleaned
    assert len(sanitize_log("x" * 5000, root, 100)) == 100


def test_symlink_detection_is_enforced_without_os_link_privileges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Covers the link checks on machines where creating real symlinks is not allowed."""
    real_is_symlink = Path.is_symlink
    with factory(tmp_path).create("responsive-hero", EDITABLE) as ws:
        linked = ws.root / "src"
        monkeypatch.setattr(
            Path, "is_symlink", lambda self: self == linked or real_is_symlink(self)
        )
        with pytest.raises(WorkspacePathError, match="links"):
            ws.write_text("src/styles.css", "hijacked")
        monkeypatch.setattr(Path, "is_symlink", real_is_symlink)
        assert ws.read_text("src/styles.css") != "hijacked"

    monkeypatch.setattr(Path, "is_symlink", lambda self: self.name == "build.mjs")
    with (
        pytest.raises(ApplicationEnvironmentError, match="links"),
        factory(tmp_path).create("responsive-hero", EDITABLE),
    ):
        pass
