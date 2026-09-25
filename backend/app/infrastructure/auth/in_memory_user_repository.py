import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from app.domains.auth import ApplicationUser, AuthenticatedIdentity, AuthProvider


class InMemoryUserRepository:
    def __init__(self) -> None:
        self._users: dict[tuple[AuthProvider, str], ApplicationUser] = {}
        self._lock = asyncio.Lock()

    @property
    def users(self) -> tuple[ApplicationUser, ...]:
        return tuple(self._users.values())

    async def find_by_external_identity(
        self,
        provider: AuthProvider,
        provider_user_id: str,
    ) -> ApplicationUser | None:
        return self._users.get((provider, provider_user_id))

    async def synchronize(self, identity: AuthenticatedIdentity) -> ApplicationUser:
        key = (identity.provider, identity.provider_user_id)
        async with self._lock:
            existing = self._users.get(key)
            now = datetime.now(UTC)
            if existing is None:
                user = ApplicationUser(
                    id=str(uuid4()),
                    auth_provider=identity.provider,
                    auth_provider_user_id=identity.provider_user_id,
                    email=identity.email,
                    username=None,
                    created_at=now,
                    updated_at=now,
                )
            elif identity.email is not None and existing.email != identity.email:
                user = replace(existing, email=identity.email, updated_at=now)
            else:
                user = existing
            self._users[key] = user
            return user
