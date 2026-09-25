import asyncio

from app.application.auth import ResolveAuthenticatedUserUseCase
from app.domains.auth import AuthenticatedIdentity, AuthProvider
from app.infrastructure.auth import InMemoryUserRepository


class FakeAccessTokenVerifier:
    def __init__(self, identity: AuthenticatedIdentity) -> None:
        self.identity = identity
        self.tokens: list[str] = []

    async def verify(self, access_token: str) -> AuthenticatedIdentity:
        self.tokens.append(access_token)
        return self.identity


def test_first_access_creates_user_and_repeated_access_returns_same_user() -> None:
    identity = AuthenticatedIdentity(
        provider=AuthProvider.SUPABASE,
        provider_user_id="provider-user-1",
        email="first@example.com",
    )
    verifier = FakeAccessTokenVerifier(identity)
    repository = InMemoryUserRepository()
    use_case = ResolveAuthenticatedUserUseCase(verifier, repository)

    first = asyncio.run(use_case.execute("token-one"))
    second = asyncio.run(use_case.execute("token-two"))

    assert first == second
    assert len(repository.users) == 1
    assert verifier.tokens == ["token-one", "token-two"]


def test_user_sync_updates_email_but_absent_email_does_not_erase_it() -> None:
    repository = InMemoryUserRepository()
    original = AuthenticatedIdentity(
        AuthProvider.SUPABASE,
        "provider-user-1",
        "old@example.com",
    )
    changed = AuthenticatedIdentity(
        AuthProvider.SUPABASE,
        "provider-user-1",
        "new@example.com",
    )
    absent = AuthenticatedIdentity(AuthProvider.SUPABASE, "provider-user-1", None)

    first = asyncio.run(repository.synchronize(original))
    updated = asyncio.run(repository.synchronize(changed))
    preserved = asyncio.run(repository.synchronize(absent))

    assert updated.id == first.id
    assert updated.email == "new@example.com"
    assert preserved.email == "new@example.com"
    assert len(repository.users) == 1


def test_concurrent_first_access_creates_one_local_user() -> None:
    identity = AuthenticatedIdentity(AuthProvider.SUPABASE, "same-provider-user", None)
    repository = InMemoryUserRepository()

    async def synchronize_concurrently() -> list[str]:
        users = await asyncio.gather(*(repository.synchronize(identity) for _ in range(10)))
        return [user.id for user in users]

    user_ids = asyncio.run(synchronize_concurrently())

    assert len(set(user_ids)) == 1
    assert len(repository.users) == 1
