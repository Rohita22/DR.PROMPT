import asyncio
from datetime import UTC, datetime

import pytest

from app.application.leaderboard import GetChallengeLeaderboardUseCase
from app.application.leaderboard.errors import LeaderboardRequestError
from app.domains.challenges.errors import ChallengeNotFoundError
from app.domains.leaderboard import LeaderboardPage, RankedLeaderboardSubmission
from app.infrastructure.challenges import InMemoryChallengeRepository


class CapturingLeaderboardReader:
    def __init__(self, page: LeaderboardPage) -> None:
        self.page = page
        self.arguments: dict[str, object] | None = None

    async def get_page(self, **arguments: object) -> LeaderboardPage:
        self.arguments = arguments
        return self.page


def ranked(rank: int, user_id: str, username: str | None = None) -> RankedLeaderboardSubmission:
    return RankedLeaderboardSubmission(
        rank=rank,
        submission_id=f"submission-{rank}",
        user_id=user_id,
        username=username,
        score=95 - rank,
        accuracy=90,
        prompt_tokens=40 + rank,
        stars=2,
        submitted_at=datetime(2026, 1, rank, tzinfo=UTC),
    )


def test_use_case_scopes_query_to_active_version_and_model() -> None:
    own = ranked(18, "current-user")
    reader = CapturingLeaderboardReader(LeaderboardPage((ranked(1, "other", "aiwizard"),), 18, own))
    result = asyncio.run(
        GetChallengeLeaderboardUseCase(InMemoryChallengeRepository(), reader).execute(
            "exact-output", limit=1, offset=0, current_user_id="current-user"
        )
    )

    assert reader.arguments == {
        "challenge_id": "control-exact-output",
        "challenge_version_id": "1",
        "model_identifier": "openai/gpt-oss-20b",
        "model_configuration_version": "exact-output-model-v1",
        "limit": 1,
        "offset": 0,
        "current_user_id": "current-user",
    }
    assert result.entries[0].player == "aiwizard"
    assert result.entries[0].is_current_user is False
    assert result.current_user_entry is not None
    assert result.current_user_entry.rank == 18
    assert result.current_user_entry.is_current_user is True
    assert result.total_entries == 18
    assert result.has_more is True


def test_unknown_challenge_and_invalid_pagination_fail_predictably() -> None:
    reader = CapturingLeaderboardReader(LeaderboardPage((), 0, None))
    use_case = GetChallengeLeaderboardUseCase(InMemoryChallengeRepository(), reader)

    with pytest.raises(ChallengeNotFoundError):
        asyncio.run(use_case.execute("missing"))
    with pytest.raises(LeaderboardRequestError):
        asyncio.run(use_case.execute("exact-output", limit=101))
    with pytest.raises(LeaderboardRequestError):
        asyncio.run(use_case.execute("exact-output", offset=-1))
