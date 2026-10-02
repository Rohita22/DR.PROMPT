import base64
import hashlib
from contextlib import AbstractAsyncContextManager
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Protocol

from app.application.challenges.models import ApplicationSubmitResult
from app.core.exceptions import ApplicationIdempotencyKeyError
from app.domains.challenges.models import Difficulty
from app.domains.execution import AgentStatus, ScreenshotArtifact
from app.domains.progression import XPRewardConfiguration
from app.domains.submissions import Submission


class ApplicationExecutionKind(StrEnum):
    RUN = "run"
    SUBMIT = "submit"


@dataclass(frozen=True, slots=True)
class ApplicationExecutionScope:
    user_id: str
    challenge_id: str
    challenge_slug: str
    challenge_version_id: str


@dataclass(frozen=True, slots=True)
class ApplicationExecutionStart:
    reservation_id: str | None = None
    replay: ApplicationSubmitResult | None = None


class ApplicationExecutionCoordinator(Protocol):
    def start(
        self,
        scope: ApplicationExecutionScope,
        *,
        kind: ApplicationExecutionKind,
        cooldown_seconds: int,
        stale_after_seconds: int,
        idempotency_key_hash: str | None = None,
    ) -> AbstractAsyncContextManager[ApplicationExecutionStart]: ...


class ApplicationExecutionService:
    """APPLICATION-only policy over a cross-instance coordination adapter."""

    def __init__(
        self,
        coordinator: ApplicationExecutionCoordinator,
        *,
        run_cooldown_seconds: int,
        submit_cooldown_seconds: int,
        stale_after_seconds: int,
    ) -> None:
        self._coordinator = coordinator
        self._run_cooldown = run_cooldown_seconds
        self._submit_cooldown = submit_cooldown_seconds
        self._stale_after = stale_after_seconds

    def run(
        self, scope: ApplicationExecutionScope
    ) -> AbstractAsyncContextManager[ApplicationExecutionStart]:
        return self._coordinator.start(
            scope,
            kind=ApplicationExecutionKind.RUN,
            cooldown_seconds=self._run_cooldown,
            stale_after_seconds=self._stale_after,
        )

    def submit(
        self,
        scope: ApplicationExecutionScope,
        idempotency_key: str | None,
    ) -> AbstractAsyncContextManager[ApplicationExecutionStart]:
        key = (idempotency_key or "").strip()
        if not 8 <= len(key) <= 255 or any(ord(character) < 33 for character in key):
            raise ApplicationIdempotencyKeyError()
        return self._coordinator.start(
            scope,
            kind=ApplicationExecutionKind.SUBMIT,
            cooldown_seconds=self._submit_cooldown,
            stale_after_seconds=self._stale_after,
            idempotency_key_hash=hashlib.sha256(key.encode()).hexdigest(),
        )


def application_submit_result_to_payload(result: ApplicationSubmitResult) -> dict[str, object]:
    payload = asdict(result)
    payload["agent_status"] = result.agent_status.value
    if result.screenshot is not None:
        payload["screenshot"] = {
            "viewport": result.screenshot.viewport,
            "label": result.screenshot.label,
            "width": result.screenshot.width,
            "height": result.screenshot.height,
            "png_base64": base64.b64encode(result.screenshot.png).decode("ascii"),
        }
    return payload


def application_submit_result_from_payload(payload: dict[str, object]) -> ApplicationSubmitResult:
    screenshot_data = payload.get("screenshot")
    screenshot = None
    if isinstance(screenshot_data, dict):
        screenshot = ScreenshotArtifact(
            viewport=str(screenshot_data["viewport"]),
            label=str(screenshot_data.get("label", "")),
            width=int(screenshot_data["width"]),
            height=int(screenshot_data["height"]),
            png=base64.b64decode(str(screenshot_data["png_base64"]), validate=True),
        )
    return ApplicationSubmitResult(
        challenge_slug=str(payload["challenge_slug"]),
        challenge_version_id=str(payload["challenge_version_id"]),
        passed_count=int(payload["passed_count"]),
        total_count=int(payload["total_count"]),
        evaluation_score=float(payload["evaluation_score"]),
        prompt_tokens=int(payload["prompt_tokens"]),
        efficiency=float(payload["efficiency"]),
        final_score=float(payload["final_score"]),
        stars=int(payload["stars"]),
        xp_earned=int(payload["xp_earned"]),
        total_xp=int(payload["total_xp"]),
        best_score=float(payload["best_score"]),
        best_stars=int(payload["best_stars"]),
        completed=bool(payload["completed"]),
        agent_status=AgentStatus(str(payload["agent_status"])),
        screenshot=screenshot,
    )


class ApplicationSubmissionRepository(Protocol):
    async def save_application_with_progression(
        self,
        submission: Submission,
        *,
        difficulty: Difficulty,
        xp_configuration: XPRewardConfiguration,
        reservation_id: str,
        result: ApplicationSubmitResult,
    ) -> ApplicationSubmitResult: ...
