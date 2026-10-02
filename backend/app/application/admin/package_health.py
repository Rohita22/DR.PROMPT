"""Package health executes the pristine starter with no agent or gameplay writes."""

from app.domains.application.sandbox import ExecutionMode
from app.domains.execution.models import BuildStatus


class ApplicationPackageHealth:
    def __init__(self, packages, workspaces, sandbox, static_evaluator):
        self.packages, self.workspaces = packages, workspaces
        self.sandbox, self.static_evaluator = sandbox, static_evaluator

    async def execute(self, package_id: str):
        package = self.packages.load(package_id)
        config = package.defaults
        executable = config.execution_mode == ExecutionMode.SANDBOXED_EXECUTABLE
        if executable and not (await self.sandbox.capability()).available:
            return {
                "package": package.id,
                "available": False,
                "code": "sandbox_unavailable",
                "build_succeeded": None,
                "checks_initialized": False,
            }
        with self.workspaces.create(package.id, config.editable_files) as workspace:
            if executable:
                result = await self.sandbox.inspect(
                    workspace, config, package, package.selected_checks(config.visible_checks)
                )
            else:
                result = await self.static_evaluator.inspect(workspace, config, package)
        return {
            "package": package.id,
            "available": True,
            "code": None,
            "build_succeeded": result.build.status == BuildStatus.PASSED,
            "checks_initialized": bool(result.screenshots),
        }
