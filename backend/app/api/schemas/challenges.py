import base64
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from app.application.challenges.models import (
    ApplicationRunResult,
    ApplicationSubmitResult,
    RunChallengeResult,
    SubmitChallengeResult,
)
from app.application.leaderboard import ChallengeLeaderboardResult, LeaderboardEntryResult
from app.domains.challenges.models import PlayableChallenge
from app.domains.execution import ScreenshotArtifact
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
    challenge_type: str
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
            challenge_type=playable.version.challenge_type.value,
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


class ApplicationBriefResponse(BaseModel):
    """Public APPLICATION facts only; checks and execution configuration are excluded."""

    editable_files: list[str]
    starter_preview_viewports: list[str]
    execution_mode: str = "static"
    available: bool = True


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
    challenge_type: str
    application: ApplicationBriefResponse | None

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
            challenge_type=playable.version.challenge_type.value,
            application=(
                ApplicationBriefResponse(
                    execution_mode=playable.version.application_config.execution_mode.value,
                    editable_files=list(playable.version.application_config.editable_files),
                    starter_preview_viewports=[
                        v.id for v in playable.version.application_config.viewports if v.screenshot
                    ],
                )
                if playable.version.application_config is not None
                else None
            ),
        )


class LeaderboardEntryResponse(BaseModel):
    rank: int
    player: str
    score: float
    accuracy: float
    prompt_tokens: int
    stars: int
    submitted_at: datetime
    is_current_user: bool

    @classmethod
    def from_application_result(cls, entry: LeaderboardEntryResult) -> "LeaderboardEntryResponse":
        return cls(
            rank=entry.rank,
            player=entry.player,
            score=round(entry.score, 2),
            accuracy=round(entry.accuracy, 2),
            prompt_tokens=entry.prompt_tokens,
            stars=entry.stars,
            submitted_at=entry.submitted_at,
            is_current_user=entry.is_current_user,
        )


class ChallengeLeaderboardResponse(BaseModel):
    challenge: str
    version: str
    entries: list[LeaderboardEntryResponse]
    current_user_entry: LeaderboardEntryResponse | None
    total_entries: int
    limit: int
    offset: int
    has_more: bool

    @classmethod
    def from_application_result(
        cls,
        result: ChallengeLeaderboardResult,
    ) -> "ChallengeLeaderboardResponse":
        return cls(
            challenge=result.challenge_slug,
            version=result.challenge_version_id,
            entries=[
                LeaderboardEntryResponse.from_application_result(item) for item in result.entries
            ],
            current_user_entry=(
                LeaderboardEntryResponse.from_application_result(result.current_user_entry)
                if result.current_user_entry is not None
                else None
            ),
            total_entries=result.total_entries,
            limit=result.limit,
            offset=result.offset,
            has_more=result.has_more,
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


class ScreenshotResponse(BaseModel):
    label: str
    viewport: str
    width: int
    height: int
    image: str = Field(description="PNG data URI of the rendered result.")

    @classmethod
    def from_artifact(cls, artifact: ScreenshotArtifact) -> "ScreenshotResponse":
        encoded = base64.b64encode(artifact.png).decode("ascii")
        return cls(
            viewport=artifact.viewport,
            label=artifact.label or artifact.viewport,
            width=artifact.width,
            height=artifact.height,
            image=f"data:image/png;base64,{encoded}",
        )


class ApplicationAgentResponse(BaseModel):
    status: Literal["applied", "rejected"]
    message: str | None


class ChangedFileResponse(BaseModel):
    path: str
    additions: int
    deletions: int


class ApplicationBuildResponse(BaseModel):
    status: Literal["passed", "failed", "skipped"]
    log: str


class ApplicationCheckResponse(BaseModel):
    id: str
    label: str
    passed: bool
    message: str | None


class ApplicationRunResponse(BaseModel):
    """Visible APPLICATION Run feedback. Contains only visible checks."""

    challenge_type: Literal["application"] = "application"
    challenge: str
    challenge_id: str
    version: str
    passed: int
    total: int
    evaluation_score: float
    agent: ApplicationAgentResponse
    changed_files: list[ChangedFileResponse]
    build: ApplicationBuildResponse
    checks: list[ApplicationCheckResponse]
    screenshots: list[ScreenshotResponse]

    @classmethod
    def from_application_result(cls, result: ApplicationRunResult) -> "ApplicationRunResponse":
        return cls(
            challenge=result.challenge_slug,
            challenge_id=result.challenge_id,
            version=result.challenge_version_id,
            passed=result.passed_count,
            total=result.total_count,
            evaluation_score=round(result.evaluation_score, 2),
            agent=ApplicationAgentResponse(
                status=result.changes.agent_status.value,
                message=result.changes.message,
            ),
            changed_files=[
                ChangedFileResponse(
                    path=item.path, additions=item.additions, deletions=item.deletions
                )
                for item in result.changes.files
            ],
            build=ApplicationBuildResponse(status=result.build.status.value, log=result.build.log),
            checks=[
                ApplicationCheckResponse(
                    id=check.check_id, label=check.label, passed=check.passed, message=check.message
                )
                for check in result.checks
            ],
            screenshots=[ScreenshotResponse.from_artifact(item) for item in result.screenshots],
        )


class ApplicationSubmitResponse(BaseModel):
    """Aggregate-only hidden APPLICATION evaluation; no per-check field is representable."""

    challenge_type: Literal["application"] = "application"
    challenge: str
    version: str
    passed: int
    total: int
    evaluation_score: float
    prompt_tokens: int
    efficiency: float
    score: float
    stars: int
    xp_earned: int
    total_xp: int
    best_score: float
    best_stars: int
    completed: bool
    agent_status: Literal["applied", "rejected"]
    screenshot: ScreenshotResponse | None

    @classmethod
    def from_application_result(
        cls,
        result: ApplicationSubmitResult,
    ) -> "ApplicationSubmitResponse":
        return cls(
            challenge=result.challenge_slug,
            version=result.challenge_version_id,
            passed=result.passed_count,
            total=result.total_count,
            evaluation_score=round(result.evaluation_score, 2),
            prompt_tokens=result.prompt_tokens,
            efficiency=round(result.efficiency, 2),
            score=result.final_score,
            stars=result.stars,
            xp_earned=result.xp_earned,
            total_xp=result.total_xp,
            best_score=result.best_score,
            best_stars=result.best_stars,
            completed=result.completed,
            agent_status=result.agent_status.value,
            screenshot=(
                ScreenshotResponse.from_artifact(result.screenshot)
                if result.screenshot is not None
                else None
            ),
        )
