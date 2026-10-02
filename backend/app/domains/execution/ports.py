from typing import Protocol

from app.domains.execution.models import ChallengeExecutionRequest, ChallengeExecutionResult


class ChallengeExecutor(Protocol):
    """Executes one challenge family's environment and returns a normalized result.

    `execute_visible` backs Run and may be reported in detail. `execute_hidden` backs Submit;
    its result describes server-only checks and must be reduced to aggregates by the caller.
    """

    async def execute_visible(
        self,
        request: ChallengeExecutionRequest,
    ) -> ChallengeExecutionResult: ...

    async def execute_hidden(
        self,
        request: ChallengeExecutionRequest,
    ) -> ChallengeExecutionResult: ...
