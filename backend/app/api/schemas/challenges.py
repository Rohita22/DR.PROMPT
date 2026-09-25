from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from app.application.challenges.models import RunChallengeResult, SubmitChallengeResult
from app.domains.challenges.models import PlayableChallenge
from app.domains.progression import ChallengeAccess


class ChallengePromptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1)

    @field_validator("prompt")
    @classmethod
    def prompt_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Prompt cannot be blank.")
        return value


class RunChallengeRequest(ChallengePromptRequest):
    pass


class SubmitChallengeRequest(ChallengePromptRequest):
    pass


class ChallengeListItemResponse(BaseModel):
    id: str
    slug: str
    title: str
    track: str
    difficulty: str
    order: int
    status: str
    best_score: float | None
    best_stars: int
    attempts: int
    completed: bool

    @classmethod
    def from_access(cls, access: ChallengeAccess) -> "ChallengeListItemResponse":
        playable = access.challenge
        return cls(
            id=playable.challenge.id,
            slug=playable.challenge.slug,
            title=playable.version.title,
            track=playable.challenge.track.value,
            difficulty=playable.version.difficulty.value,
            order=playable.challenge.order,
            status=access.status.value,
            best_score=(round(access.best_score, 2) if access.best_score is not None else None),
            best_stars=access.best_stars,
            attempts=access.attempts,
            completed=access.completed,
        )


class ChallengeListResponse(BaseModel):
    challenges: list[ChallengeListItemResponse]


class VisibleExampleResponse(BaseModel):
    input: JsonValue
    expected: JsonValue
    explanation: str | None


class ChallengeDetailResponse(BaseModel):
    id: str
    slug: str
    title: str
    description: str
    objective: str
    constraints: list[str]
    track: str
    difficulty: str
    order: int
    version: str
    prompt_token_limit: int | None
    status: str
    best_score: float | None
    best_stars: int
    attempts: int
    completed: bool
    examples: list[VisibleExampleResponse]

    @classmethod
    def from_domain(
        cls,
        playable: PlayableChallenge,
        access: ChallengeAccess,
    ) -> "ChallengeDetailResponse":
        return cls(
            id=playable.challenge.id,
            slug=playable.challenge.slug,
            title=playable.version.title,
            description=playable.version.description,
            objective=playable.version.objective,
            constraints=list(playable.version.constraints),
            track=playable.challenge.track.value,
            difficulty=playable.version.difficulty.value,
            order=playable.challenge.order,
            version=playable.version.version_id,
            prompt_token_limit=playable.version.prompt_token_limit,
            status=access.status.value,
            best_score=(round(access.best_score, 2) if access.best_score is not None else None),
            best_stars=access.best_stars,
            attempts=access.attempts,
            completed=access.completed,
            examples=[
                VisibleExampleResponse(
                    input=example.input,
                    expected=example.expected_output,
                    explanation=example.explanation,
                )
                for example in playable.version.visible_examples
            ],
        )


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


class SubmitChallengeResponse(BaseModel):
    """Aggregate-only response; hidden per-test data has no representable field."""

    challenge: str
    version: str
    passed: int
    total: int
    accuracy: float
    prompt_tokens: int
    efficiency: float
    score: float
    stars: int
    xp_earned: int
    total_xp: int
    best_score: float
    best_stars: int
    completed: bool

    @classmethod
    def from_application_result(
        cls,
        result: SubmitChallengeResult,
    ) -> "SubmitChallengeResponse":
        return cls(
            challenge=result.challenge_slug,
            version=result.challenge_version_id,
            passed=result.passed_count,
            total=result.total_count,
            accuracy=round(result.accuracy, 2),
            prompt_tokens=result.prompt_tokens,
            efficiency=round(result.efficiency, 2),
            score=result.final_score,
            stars=result.stars,
            xp_earned=result.xp_earned,
            total_xp=result.total_xp,
            best_score=result.best_score,
            best_stars=result.best_stars,
            completed=result.completed,
        )
