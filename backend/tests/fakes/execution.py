from app.domains.challenges import ChallengeType
from app.domains.evaluation.engine import EvaluationEngine
from app.domains.evaluation.ports import HiddenTestSuiteReader, LLMProvider
from app.domains.execution import ChallengeExecutorResolver, TextChallengeExecutor
from app.infrastructure.challenges.in_memory_hidden_test_repository import (
    InMemoryHiddenTestRepository,
)


def text_executor_resolver(
    provider: LLMProvider,
    hidden_reader: HiddenTestSuiteReader | None = None,
) -> ChallengeExecutorResolver:
    """Production-equivalent TEXT-only resolver wired with offline test doubles."""
    return ChallengeExecutorResolver(
        {
            ChallengeType.TEXT: TextChallengeExecutor(
                provider,
                EvaluationEngine.with_builtin_graders(),
                hidden_reader if hidden_reader is not None else InMemoryHiddenTestRepository(),
            )
        }
    )
