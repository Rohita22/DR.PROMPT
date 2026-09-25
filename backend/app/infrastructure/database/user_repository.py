import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PersistenceError
from app.domains.auth import ApplicationUser, AuthenticatedIdentity, AuthProvider
from app.infrastructure.database.models import UserRow


def _to_domain(row: UserRow) -> ApplicationUser:
    return ApplicationUser(
        id=str(row.id),
        auth_provider=AuthProvider(row.auth_provider),
        auth_provider_user_id=row.auth_provider_user_id,
        email=row.email,
        username=row.username,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class PostgresUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_external_identity(
        self,
        provider: AuthProvider,
        provider_user_id: str,
    ) -> ApplicationUser | None:
        try:
            async with self._session.begin():
                row = await self._find_row(provider, provider_user_id)
                return _to_domain(row) if row is not None else None
        except SQLAlchemyError:
            raise PersistenceError("Database operation failed.") from None

    async def synchronize(self, identity: AuthenticatedIdentity) -> ApplicationUser:
        try:
            async with self._session.begin():
                row = await self._find_row(identity.provider, identity.provider_user_id)
                if row is None:
                    row = UserRow(
                        id=uuid.uuid4(),
                        auth_provider=identity.provider.value,
                        auth_provider_user_id=identity.provider_user_id,
                        email=identity.email,
                        username=None,
                    )
                    self._session.add(row)
                elif identity.email is not None and row.email != identity.email:
                    row.email = identity.email
                await self._session.flush()
                return _to_domain(row)
        except IntegrityError:
            return await self._load_after_concurrent_insert(identity)
        except SQLAlchemyError:
            raise PersistenceError("Database operation failed.") from None

    async def _load_after_concurrent_insert(
        self,
        identity: AuthenticatedIdentity,
    ) -> ApplicationUser:
        try:
            async with self._session.begin():
                row = await self._find_row(identity.provider, identity.provider_user_id)
                if row is None:
                    raise PersistenceError("User synchronization failed.")
                if identity.email is not None and row.email != identity.email:
                    row.email = identity.email
                    await self._session.flush()
                return _to_domain(row)
        except PersistenceError:
            raise
        except SQLAlchemyError:
            raise PersistenceError("Database operation failed.") from None

    async def _find_row(
        self,
        provider: AuthProvider,
        provider_user_id: str,
    ) -> UserRow | None:
        return await self._session.scalar(
            select(UserRow).where(
                UserRow.auth_provider == provider.value,
                UserRow.auth_provider_user_id == provider_user_id,
            )
        )
