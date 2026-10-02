from collections.abc import Mapping
from types import MappingProxyType

from app.domains.challenges.models import ChallengeType
from app.domains.execution.errors import UnsupportedChallengeTypeError
from app.domains.execution.ports import ChallengeExecutor


class ChallengeExecutorResolver:
    """Explicit, per-instance challenge type → executor mapping."""

    def __init__(self, executors: Mapping[ChallengeType, ChallengeExecutor]) -> None:
        self._executors = MappingProxyType(dict(executors))

    def resolve(self, challenge_type: ChallengeType) -> ChallengeExecutor:
        executor = self._executors.get(challenge_type)
        if executor is None:
            raise UnsupportedChallengeTypeError(str(challenge_type))
        return executor
