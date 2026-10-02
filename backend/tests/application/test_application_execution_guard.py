import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import pytest

from app.application.challenges.execution_guard import (
    ApplicationExecutionKind,
    ApplicationExecutionScope,
    ApplicationExecutionService,
    ApplicationExecutionStart,
)
from app.core.exceptions import (
    ApplicationExecutionInProgressError,
    ApplicationIdempotencyKeyError,
    ApplicationRateLimitError,
)


@dataclass
class FakeCoordinator:
    now: float = 100.0
    active: set[str] = field(default_factory=set)
    starts: dict[tuple[str, ApplicationExecutionKind], float] = field(default_factory=dict)

    @asynccontextmanager
    async def start(
        self,
        scope: ApplicationExecutionScope,
        *,
        kind: ApplicationExecutionKind,
        cooldown_seconds: int,
        stale_after_seconds: int,
        idempotency_key_hash: str | None = None,
    ):
        del stale_after_seconds, idempotency_key_hash
        if scope.user_id in self.active:
            raise ApplicationExecutionInProgressError()
        previous = self.starts.get((scope.user_id, kind))
        if previous is not None and self.now < previous + cooldown_seconds:
            raise ApplicationRateLimitError(int(previous + cooldown_seconds - self.now), kind.value)
        self.active.add(scope.user_id)
        self.starts[(scope.user_id, kind)] = self.now
        try:
            yield ApplicationExecutionStart(
                reservation_id="reservation" if kind is ApplicationExecutionKind.SUBMIT else None
            )
        finally:
            self.active.remove(scope.user_id)


def scope(user_id: str = "user-a") -> ApplicationExecutionScope:
    return ApplicationExecutionScope(user_id, "challenge", "responsive-hero", "1")


def service(coordinator: FakeCoordinator) -> ApplicationExecutionService:
    return ApplicationExecutionService(
        coordinator,
        run_cooldown_seconds=10,
        submit_cooldown_seconds=20,
        stale_after_seconds=180,
    )


def test_run_cooldown_is_per_user_and_uses_an_injectable_clock() -> None:
    coordinator = FakeCoordinator()
    guard = service(coordinator)

    async def exercise() -> None:
        async with guard.run(scope()):
            pass
        with pytest.raises(ApplicationRateLimitError) as rejected:
            async with guard.run(scope()):
                pass
        assert rejected.value.retry_after_seconds == 10
        async with guard.run(scope("user-b")):
            pass
        coordinator.now += 10
        async with guard.run(scope()):
            pass

    asyncio.run(exercise())


def test_run_and_submit_share_concurrency_but_have_independent_cooldowns() -> None:
    coordinator = FakeCoordinator()
    guard = service(coordinator)

    async def exercise() -> None:
        entered = asyncio.Event()
        release = asyncio.Event()

        async def hold_run() -> None:
            async with guard.run(scope()):
                entered.set()
                await release.wait()

        task = asyncio.create_task(hold_run())
        await entered.wait()
        with pytest.raises(ApplicationExecutionInProgressError):
            async with guard.submit(scope(), "submit-key-123"):
                pass
        async with guard.run(scope("user-b")):
            pass
        release.set()
        await task
        async with guard.submit(scope(), "submit-key-123"):
            pass

    asyncio.run(exercise())


def test_lock_is_released_after_execution_exception() -> None:
    coordinator = FakeCoordinator()
    guard = ApplicationExecutionService(
        coordinator,
        run_cooldown_seconds=0,
        submit_cooldown_seconds=0,
        stale_after_seconds=180,
    )

    async def exercise() -> None:
        with pytest.raises(TimeoutError):
            async with guard.run(scope()):
                raise TimeoutError
        async with guard.submit(scope(), "submit-key-123"):
            pass

    asyncio.run(exercise())


def test_application_submit_requires_a_bounded_opaque_key() -> None:
    guard = service(FakeCoordinator())
    with pytest.raises(ApplicationIdempotencyKeyError):
        guard.submit(scope(), None)
    with pytest.raises(ApplicationIdempotencyKeyError):
        guard.submit(scope(), "short")
