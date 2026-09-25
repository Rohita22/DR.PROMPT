from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.core.exceptions import DomainError
from app.domains.submissions import Submission


def valid_submission() -> Submission:
    return Submission(
        id="80afd028-26a1-4fe8-aae6-982c322fa7cf",
        challenge_id="control-exact-output",
        challenge_version_id="1",
        user_id=None,
        prompt="Return YES or NO.",
        prompt_tokens=5,
        passed_tests=5,
        total_tests=6,
        accuracy=83.33,
        efficiency=100,
        final_score=86.66,
        stars=1,
        model_identifier="openai/gpt-oss-20b",
        model_configuration_version="exact-output-model-v1",
        created_at=datetime.now(UTC),
    )


def test_completed_submission_accepts_reproducible_score_data() -> None:
    submission = valid_submission()

    assert submission.total_tests == 6
    assert submission.user_id is None
    assert submission.created_at.utcoffset() is not None


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"prompt_tokens": -1}, "token count"),
        ({"passed_tests": 7}, "test counts"),
        ({"total_tests": 0, "passed_tests": 0}, "test counts"),
        ({"accuracy": 101}, "scores"),
        ({"efficiency": -1}, "scores"),
        ({"final_score": float("nan")}, "scores"),
        ({"stars": 4}, "stars"),
        ({"model_identifier": " "}, "model metadata"),
        ({"created_at": datetime.now()}, "timezone-aware"),
    ],
)
def test_submission_rejects_invalid_persisted_state(
    changes: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(DomainError, match=message):
        replace(valid_submission(), **changes)
