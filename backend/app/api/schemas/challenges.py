from pydantic import BaseModel, Field, JsonValue, field_validator

from app.application.challenges.models import RunChallengeResult


class RunChallengeRequest(BaseModel):
    prompt: str = Field(min_length=1)

    @field_validator("prompt")
    @classmethod
    def prompt_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Prompt cannot be blank.")
        return value


class VisibleTestRunResponse(BaseModel):
    id: str
    input: JsonValue
    expected: JsonValue
    actual: JsonValue
    passed: bool
    failure_reason: str | None


class RunChallengeResponse(BaseModel):
    challenge: str
    challenge_id: str
    version: str
    passed: int
    total: int
    accuracy: float
    tests: list[VisibleTestRunResponse]

    @classmethod
    def from_application_result(cls, result: RunChallengeResult) -> "RunChallengeResponse":
        return cls(
            challenge=result.challenge_slug,
            challenge_id=result.challenge_id,
            version=result.challenge_version_id,
            passed=result.passed_count,
            total=result.total_count,
            accuracy=round(result.accuracy, 2),
            tests=[
                VisibleTestRunResponse(
                    id=test.test_id,
                    input=test.input,
                    expected=test.expected_output,
                    actual=test.actual_output,
                    passed=test.passed,
                    failure_reason=(
                        test.failure_reason.value if test.failure_reason is not None else None
                    ),
                )
                for test in result.test_results
            ],
        )
