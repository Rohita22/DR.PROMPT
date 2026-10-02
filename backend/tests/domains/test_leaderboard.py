from datetime import UTC, datetime, timedelta

from app.domains.leaderboard import (
    LeaderboardSubmissionCandidate,
    leaderboard_display_name,
    rank_best_submissions,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def candidate(
    submission_id: str,
    user_id: str,
    *,
    score: float = 90,
    accuracy: float = 90,
    tokens: int = 50,
    submitted_at: datetime = NOW,
) -> LeaderboardSubmissionCandidate:
    return LeaderboardSubmissionCandidate(
        submission_id=submission_id,
        user_id=user_id,
        username=None,
        score=score,
        accuracy=accuracy,
        prompt_tokens=tokens,
        stars=2,
        submitted_at=submitted_at,
    )


def test_ranking_applies_every_product_tie_break_in_order() -> None:
    entries = rank_best_submissions(
        (
            candidate("lower-score", "u1", score=89, accuracy=100, tokens=1),
            candidate("higher-score", "u2", score=90, accuracy=80, tokens=100),
            candidate("higher-accuracy", "u3", score=90, accuracy=90, tokens=100),
            candidate("fewer-tokens", "u4", score=90, accuracy=90, tokens=50),
            candidate(
                "earlier",
                "u5",
                score=90,
                accuracy=90,
                tokens=50,
                submitted_at=NOW - timedelta(seconds=1),
            ),
            candidate("000-stable-id", "u6", score=80),
            candidate("999-stable-id", "u7", score=80),
        )
    )

    assert [entry.submission_id for entry in entries] == [
        "earlier",
        "fewer-tokens",
        "higher-accuracy",
        "higher-score",
        "lower-score",
        "000-stable-id",
        "999-stable-id",
    ]
    assert [entry.rank for entry in entries] == list(range(1, 8))


def test_only_each_users_best_submission_is_ranked() -> None:
    entries = rank_best_submissions(
        (
            candidate("inferior", "same-user", score=80),
            candidate("best-score", "same-user", score=90, accuracy=80, tokens=100),
            candidate("best-accuracy", "same-user", score=90, accuracy=90, tokens=100),
            candidate("best-tokens", "same-user", score=90, accuracy=90, tokens=40),
            candidate(
                "later-identical",
                "same-user",
                score=90,
                accuracy=90,
                tokens=40,
                submitted_at=NOW + timedelta(seconds=1),
            ),
            candidate("other-user", "other-user", score=85),
        )
    )

    assert len(entries) == 2
    assert {entry.user_id for entry in entries} == {"same-user", "other-user"}
    assert (
        next(item for item in entries if item.user_id == "same-user").submission_id == "best-tokens"
    )


def test_display_name_prefers_username_and_hashes_fallback_identity() -> None:
    assert leaderboard_display_name("  aiwizard  ", "private-user-id") == "aiwizard"
    fallback = leaderboard_display_name(None, "private-user-id")
    assert fallback.startswith("Player-")
    assert "private-user-id" not in fallback
    assert fallback == leaderboard_display_name(None, "private-user-id")
