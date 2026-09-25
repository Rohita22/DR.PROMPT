from app.domains.evaluation.errors import EvaluationConfigurationError
from app.domains.evaluation.test_cases import HiddenTestSuite
from app.infrastructure.challenges.control_fixtures import (
    CONTROL_HIDDEN_TEST_SUITES,
    EXACT_OUTPUT_HIDDEN_TEST_SUITE,
)

__all__ = [
    "CONTROL_HIDDEN_TEST_SUITES",
    "EXACT_OUTPUT_HIDDEN_TEST_SUITE",
    "InMemoryHiddenTestRepository",
]


class InMemoryHiddenTestRepository:
    """Server-only version-bound hidden test storage."""

    def __init__(
        self,
        suites: tuple[tuple[str, HiddenTestSuite], ...] | tuple[HiddenTestSuite, ...] | None = None,
    ) -> None:
        if suites is None:
            items = tuple(CONTROL_HIDDEN_TEST_SUITES.items())
        elif suites and isinstance(suites[0], HiddenTestSuite):
            items = tuple(("control-exact-output", suite) for suite in suites)
        else:
            items = suites
        by_version = {
            (challenge_id, suite.challenge_version_id): suite for challenge_id, suite in items
        }
        if len(by_version) != len(items):
            raise EvaluationConfigurationError(
                "In-memory hidden suites must have unique challenge/version identities."
            )
        self._by_version = by_version

    async def get_for_version(
        self,
        challenge_id: str,
        challenge_version_id: str,
    ) -> HiddenTestSuite | None:
        return self._by_version.get((challenge_id, challenge_version_id))
