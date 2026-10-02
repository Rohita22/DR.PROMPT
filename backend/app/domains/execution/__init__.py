"""Challenge-family execution boundary: executor contract, resolver, and family executors."""

from app.domains.execution.errors import ChallengeExecutionError, UnsupportedChallengeTypeError
from app.domains.execution.models import (
    AgentStatus,
    BuildArtifact,
    BuildStatus,
    ChallengeExecutionRequest,
    ChallengeExecutionResult,
    ChangedFile,
    ChangedFilesArtifact,
    ExecutionArtifact,
    ScreenshotArtifact,
    TextOutputArtifact,
)
from app.domains.execution.ports import ChallengeExecutor
from app.domains.execution.resolver import ChallengeExecutorResolver
from app.domains.execution.text import TextChallengeExecutor

__all__ = [
    "AgentStatus",
    "BuildArtifact",
    "BuildStatus",
    "ChallengeExecutionError",
    "ChallengeExecutionRequest",
    "ChallengeExecutionResult",
    "ChallengeExecutor",
    "ChallengeExecutorResolver",
    "ChangedFile",
    "ChangedFilesArtifact",
    "ExecutionArtifact",
    "ScreenshotArtifact",
    "TextChallengeExecutor",
    "TextOutputArtifact",
    "UnsupportedChallengeTypeError",
]
