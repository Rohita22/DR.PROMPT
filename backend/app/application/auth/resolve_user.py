from app.domains.auth import AccessTokenVerifier, ApplicationUser, UserRepository


class ResolveAuthenticatedUserUseCase:
    """Verify an access token and synchronize its stable external identity locally."""

    def __init__(
        self,
        access_token_verifier: AccessTokenVerifier,
        user_repository: UserRepository,
    ) -> None:
        self._access_token_verifier = access_token_verifier
        self._user_repository = user_repository

    async def execute(self, access_token: str) -> ApplicationUser:
        identity = await self._access_token_verifier.verify(access_token)
        return await self._user_repository.synchronize(identity)
