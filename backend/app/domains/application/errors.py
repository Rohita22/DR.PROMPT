from app.core.exceptions import DomainError


class AgentOutputError(DomainError):
    """The coding agent's response was rejected; this is a failed attempt, not an outage."""

    code = "agent_output_invalid"

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class WorkspacePathError(DomainError):
    """A write would leave the disposable workspace or touch a non-editable file."""

    code = "workspace_path_rejected"


class ApplicationEnvironmentError(DomainError):
    """Infrastructure could not execute or evaluate the application; never scored."""

    code = "application_environment_unavailable"


class ApplicationConfigurationError(DomainError):
    """Trusted application-challenge configuration is internally inconsistent."""

    code = "invalid_application_configuration"
