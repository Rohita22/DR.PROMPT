import hashlib
import math
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.application.challenges.execution_guard import (
    ApplicationExecutionKind,
    ApplicationExecutionScope,
    ApplicationExecutionStart,
    application_submit_result_from_payload,
)
from app.core.exceptions import (
    ApplicationExecutionInProgressError,
    ApplicationRateLimitError,
    PersistenceError,
)
from app.infrastructure.database.models import (
    ApplicationExecutionCooldownRow,
    ApplicationSubmitRequestRow,
    ChallengeVersionRow,
)


def _advisory_key(user_id: str) -> int:
    digest = hashlib.sha256(f"dr-prompt:application:{user_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


class PostgresApplicationExecutionCoordinator:
    """Owns a dedicated connection so a session advisory lock survives short transactions."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

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
        lock_key = _advisory_key(scope.user_id)
        connection = await self._engine.connect()
        acquired = False
        reservation_id: uuid.UUID | None = None
        try:
            acquired = bool(
                await connection.scalar(
                    text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_key}
                )
            )
            await connection.commit()
            if not acquired:
                raise ApplicationExecutionInProgressError()

            async with self._sessions(bind=connection) as session, session.begin():
                user_id = uuid.UUID(scope.user_id)
                version_id = await session.scalar(
                    select(ChallengeVersionRow.id).where(
                        ChallengeVersionRow.challenge_id == scope.challenge_id,
                        ChallengeVersionRow.version == scope.challenge_version_id,
                    )
                )
                if version_id is None:
                    raise PersistenceError("Application challenge version is unavailable.")
                now = datetime.now(UTC)

                if idempotency_key_hash is not None:
                    await session.execute(
                        delete(ApplicationSubmitRequestRow).where(
                            ApplicationSubmitRequestRow.user_id == user_id,
                            ApplicationSubmitRequestRow.status == "in_progress",
                            ApplicationSubmitRequestRow.started_at
                            <= now - timedelta(seconds=stale_after_seconds),
                        )
                    )
                    request = await session.scalar(
                        select(ApplicationSubmitRequestRow).where(
                            ApplicationSubmitRequestRow.user_id == user_id,
                            ApplicationSubmitRequestRow.challenge_version_id == version_id,
                            ApplicationSubmitRequestRow.key_hash == idempotency_key_hash,
                        )
                    )
                    if request is not None and request.status == "completed":
                        if request.result_payload is None:
                            raise PersistenceError("Stored application result is unavailable.")
                        yield ApplicationExecutionStart(
                            replay=application_submit_result_from_payload(request.result_payload)
                        )
                        return
                    if request is not None:
                        raise ApplicationExecutionInProgressError()

                cooldown = await session.scalar(
                    select(ApplicationExecutionCooldownRow).where(
                        ApplicationExecutionCooldownRow.user_id == user_id,
                        ApplicationExecutionCooldownRow.execution_kind == kind.value,
                    )
                )
                if cooldown is not None:
                    retry_at = cooldown.last_started_at + timedelta(seconds=cooldown_seconds)
                    if retry_at > now:
                        raise ApplicationRateLimitError(
                            max(1, math.ceil((retry_at - now).total_seconds())), kind.value
                        )

                statement = insert(ApplicationExecutionCooldownRow).values(
                    user_id=user_id,
                    execution_kind=kind.value,
                    last_started_at=now,
                )
                await session.execute(
                    statement.on_conflict_do_update(
                        index_elements=["user_id", "execution_kind"],
                        set_={"last_started_at": statement.excluded.last_started_at},
                    )
                )
                if idempotency_key_hash is not None:
                    reservation_id = uuid.uuid4()
                    session.add(
                        ApplicationSubmitRequestRow(
                            id=reservation_id,
                            user_id=user_id,
                            challenge_id=scope.challenge_id,
                            challenge_version_id=version_id,
                            key_hash=idempotency_key_hash,
                            status="in_progress",
                            started_at=now,
                        )
                    )

            try:
                yield ApplicationExecutionStart(
                    reservation_id=str(reservation_id) if reservation_id is not None else None
                )
            except BaseException:
                if reservation_id is not None:
                    async with self._sessions(bind=connection) as session, session.begin():
                        await session.execute(
                            delete(ApplicationSubmitRequestRow).where(
                                ApplicationSubmitRequestRow.id == reservation_id,
                                ApplicationSubmitRequestRow.status == "in_progress",
                            )
                        )
                raise
        except (
            ApplicationExecutionInProgressError,
            ApplicationRateLimitError,
            PersistenceError,
        ):
            raise
        except (SQLAlchemyError, KeyError, TypeError, ValueError):
            raise PersistenceError("Application execution coordination failed.") from None
        finally:
            if acquired:
                try:
                    await connection.execute(
                        text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key}
                    )
                    await connection.commit()
                except SQLAlchemyError:
                    await connection.invalidate()
            await connection.close()
