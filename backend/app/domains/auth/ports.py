from typing import Protocol

from app.domains.auth.models import ApplicationUser, AuthenticatedIdentity, AuthProvider


class AccessTokenVerifier(Protocol):
    async def verify(self, access_token: str) -> AuthenticatedIdentity: ...


class UserRepository(Protocol):
    async def find_by_external_identity(
        self,
        provider: AuthProvider,
        provider_user_id: str,
    ) -> ApplicationUser | None: ...

    async def synchronize(self, identity: AuthenticatedIdentity) -> ApplicationUser: ...
