"""Explicit repository package catalog. Database values never become paths."""

import json
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from app.domains.application.checks import CheckDefinition, CheckParameters
from app.domains.application.errors import (
    ApplicationConfigurationError,
    ApplicationEnvironmentError,
)
from app.domains.application.models import ApplicationChallengeConfig, normalize_relative_path
from app.domains.application.packages import ApplicationPackage
from app.domains.application.sandbox import SandboxPolicy
from app.infrastructure.application.configuration import config_from_data

APPLICATION_CHALLENGES_ROOT = Path(__file__).resolve().parents[3] / "application_challenges"
_REGISTERED = MappingProxyType(
    {
        "responsive-hero": "responsive_hero",
        "pricing-grid": "pricing_grid",
        "broken-signup-validation": "broken_signup_validation",
        "product-filter": "product_filter",
    }
)


class StarterProjectRepository:
    """Package loader plus confined starter/preview storage; no dynamic package discovery."""

    def __init__(
        self,
        root: Path = APPLICATION_CHALLENGES_ROOT,
        registrations: Mapping[str, str] = _REGISTERED,
    ) -> None:
        self._root = root.resolve()
        self._registered = MappingProxyType(dict(registrations))

    def _project_dir(self, name: str) -> Path:
        directory_name = self._registered.get(name)
        if directory_name is None:
            raise ApplicationEnvironmentError("The application package is not registered.")
        if normalize_relative_path(directory_name) != directory_name:
            raise ApplicationEnvironmentError("The package registration is invalid.")
        directory = self._confined(self._root / directory_name)
        if not directory.is_dir():
            raise ApplicationEnvironmentError("The application package is unavailable.")
        return directory

    def _confined(self, path: Path) -> Path:
        if not path.is_relative_to(self._root):
            raise ApplicationEnvironmentError("Package path is outside the repository root.")
        for part in (path, *path.parents):
            if part == self._root:
                break
            if part.is_symlink() or part.is_junction():
                raise ApplicationEnvironmentError("Package paths may not traverse links.")
        if not path.resolve().is_relative_to(self._root):
            raise ApplicationEnvironmentError("Package path escapes the repository root.")
        return path

    def load(self, name: str) -> ApplicationPackage:
        directory = self._project_dir(name)
        try:
            data = json.loads(
                self._confined(directory / "manifest.json").read_text(encoding="utf-8-sig")
            )
            if set(data) - {"sandbox"} != {
                "id",
                "display_name",
                "description",
                "defaults",
                "checks",
                "protected_paths",
            }:
                raise ValueError("Invalid manifest fields")
            package = ApplicationPackage(
                id=data["id"],
                display_name=data["display_name"],
                description=data["description"],
                defaults=config_from_data(data["defaults"]),
                checks=tuple(
                    CheckDefinition(**{**c, "parameters": CheckParameters(**c["parameters"])})
                    for c in data["checks"]
                ),
                protected_paths=tuple(data["protected_paths"]),
                sandbox=SandboxPolicy(**data["sandbox"]) if data.get("sandbox") else None,
            )
            if package.id != name:
                raise ValueError("Package identity mismatch")
            package.validate(package.defaults)
            expected_command = ("sandbox", "build") if package.sandbox else ("node", "build.mjs")
            if package.defaults.build_command != expected_command:
                raise ValueError("Unapproved build command")
            source = self.starter_dir(name)
            if package.sandbox:
                for required in (
                    "package.json",
                    "package-lock.json",
                    "tsconfig.json",
                    "src/main.tsx",
                    "index.html",
                ):
                    if not self._confined(source / required).is_file():
                        raise ValueError("Missing executable starter file")
                lock = json.loads((source / "package-lock.json").read_text(encoding="utf-8"))
                dependencies = json.loads((source / "package.json").read_text(encoding="utf-8-sig"))
                expected = {"react": "19.2.0", "react-dom": "19.2.0"}
                development = {
                    "typescript": "5.9.3",
                    "esbuild": "0.25.12",
                    "@types/react": "19.2.0",
                    "@types/react-dom": "19.2.0",
                }
                if (
                    dependencies.get("dependencies") != expected
                    or dependencies.get("devDependencies") != development
                    or dependencies.get("scripts")
                ):
                    raise ValueError("Unapproved dependency policy")
                root_lock = lock.get("packages", {}).get("", {})
                if (
                    root_lock.get("dependencies") != expected
                    or root_lock.get("devDependencies") != development
                ):
                    raise ValueError("Dependency lock does not match package")
                if lock.get("lockfileVersion") != 3:
                    raise ValueError("Executable package requires lockfile v3")
            for path in source.rglob("*"):
                self._confined(path)
            for file in (
                *package.defaults.editable_files,
                package.defaults.page_source,
                *package.protected_paths,
            ):
                if (
                    normalize_relative_path(file) != file
                    or not self._confined(source / file).is_file()
                ):
                    raise ValueError("Missing package file")
            return package
        except (OSError, ValueError, TypeError, KeyError):
            raise ApplicationConfigurationError(
                "The application package manifest is invalid."
            ) from None

    def validate(self, config: ApplicationChallengeConfig) -> ApplicationPackage:
        package = self.load(config.starter_project)
        package.validate(config)
        return package

    def catalog(self) -> tuple[ApplicationPackage, ...]:
        return tuple(self.load(name) for name in self._registered)

    def starter_dir(self, name: str) -> Path:
        starter = self._confined(self._project_dir(name) / "starter")
        if not starter.is_dir():
            raise ApplicationEnvironmentError("The starter project is unavailable.")
        return starter

    def preview_png(self, name: str, viewport: str) -> bytes | None:
        package = self.load(name)
        if viewport not in {v.id for v in package.defaults.viewports if v.screenshot}:
            return None
        path = self._confined(self._project_dir(name) / "preview" / f"{viewport}.png")
        return path.read_bytes() if path.is_file() else None
