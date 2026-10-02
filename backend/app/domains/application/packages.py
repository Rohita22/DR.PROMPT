"""Repository package policy, independent of storage and HTTP."""

from dataclasses import dataclass, fields

from app.domains.application.checks import ApplicationCheckRegistry, CheckDefinition
from app.domains.application.errors import ApplicationConfigurationError
from app.domains.application.models import ApplicationChallengeConfig
from app.domains.application.sandbox import ExecutionMode, SandboxPolicy


@dataclass(frozen=True, slots=True)
class ApplicationPackage:
    id: str
    display_name: str
    description: str
    defaults: ApplicationChallengeConfig
    checks: tuple[CheckDefinition, ...]
    protected_paths: tuple[str, ...]
    sandbox: SandboxPolicy | None = None

    def validate(self, config: ApplicationChallengeConfig) -> None:
        policy = self.defaults
        if config.execution_mode != policy.execution_mode:
            raise ApplicationConfigurationError("Execution mode is package-owned.")
        if (policy.execution_mode == ExecutionMode.SANDBOXED_EXECUTABLE) != (
            self.sandbox is not None
        ):
            raise ApplicationConfigurationError("Executable packages require sandbox policy.")
        if self.sandbox and any(
            not p.startswith("src/") or p.endswith((".test.ts", ".spec.ts"))
            for p in policy.editable_files
        ):
            raise ApplicationConfigurationError("Only declared application source may be edited.")
        if config.starter_project != self.id:
            raise ApplicationConfigurationError("Package reference does not match its policy.")
        if not set(config.editable_files) <= set(policy.editable_files):
            raise ApplicationConfigurationError("Editable files exceed package policy.")
        if (config.page_source, config.build_command, config.build_output) != (
            policy.page_source,
            policy.build_command,
            policy.build_output,
        ):
            raise ApplicationConfigurationError("Build and entry settings are package-owned.")
        if set(config.editable_files) & set(self.protected_paths):
            raise ApplicationConfigurationError("Protected package files cannot be edited.")
        for field in fields(config.limits):
            if getattr(config.limits, field.name) > getattr(policy.limits, field.name):
                raise ApplicationConfigurationError("Execution limits exceed package policy.")
        if not set(config.visible_checks) <= set(policy.visible_checks):
            raise ApplicationConfigurationError("Visible checks exceed package policy.")
        if not set(config.hidden_checks) <= set(policy.hidden_checks):
            raise ApplicationConfigurationError("Hidden checks exceed package policy.")
        views = {v.id: v for v in config.viewports}
        policy_views = {v.id: v for v in policy.viewports}
        if set(views) != set(policy_views):
            raise ApplicationConfigurationError("Measurement views are package-owned.")
        for name, view in views.items():
            expected = policy_views[name]
            if (view.width, view.height) != (expected.width, expected.height):
                raise ApplicationConfigurationError("Measurement dimensions are package-owned.")
            if view.screenshot and not expected.screenshot:
                raise ApplicationConfigurationError(
                    "Private measurement views cannot be screenshots."
                )
        registry = ApplicationCheckRegistry()
        definitions = {c.id: c for c in self.checks}
        if len(definitions) != len(self.checks):
            raise ApplicationConfigurationError("Package check IDs must be unique.")
        for name in (*config.visible_checks, *config.hidden_checks):
            if name not in definitions:
                raise ApplicationConfigurationError(
                    "Selected check is not registered in the package."
                )
            check = definitions[name]
            registry.validate(check)
            if not set(check.parameters.viewports) <= views.keys():
                raise ApplicationConfigurationError("Check references an unknown viewport.")

    def selected_checks(self, ids: tuple[str, ...]) -> tuple[CheckDefinition, ...]:
        definitions = {c.id: c for c in self.checks}
        return tuple(definitions[name] for name in ids)

    @property
    def selectors(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(s for c in self.checks for s in c.parameters.selectors))
