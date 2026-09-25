import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.core.exceptions import AuthenticationError, AuthenticationServiceError
from app.domains.auth import AuthProvider
from app.infrastructure.auth.supabase_jwt import SupabaseAccessTokenVerifier

ISSUER = "https://project.supabase.co/auth/v1"
AUDIENCE = "authenticated"
KEY_ID = "test-signing-key"
PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC_JWK = RSAAlgorithm.to_jwk(PRIVATE_KEY.public_key(), as_dict=True)
PUBLIC_JWK.update({"kid": KEY_ID, "alg": "RS256", "use": "sig"})


def make_token(
    *,
    private_key: object = PRIVATE_KEY,
    key_id: str = KEY_ID,
    issuer: str = ISSUER,
    expires_at: datetime | None = None,
    include_subject: bool = True,
) -> str:
    claims: dict[str, object] = {
        "iss": issuer,
        "aud": AUDIENCE,
        "exp": expires_at or datetime.now(UTC) + timedelta(minutes=5),
        "email": "player@example.com",
    }
    if include_subject:
        claims["sub"] = "supabase-user-123"
    return jwt.encode(
        claims,
        private_key,
        algorithm="RS256",
        headers={"kid": key_id},
    )


class CountingJwksFetcher:
    def __init__(self, document: Mapping[str, object]) -> None:
        self.document = document
        self.calls = 0

    async def __call__(self) -> Mapping[str, object]:
        self.calls += 1
        return self.document


def verifier(fetcher: CountingJwksFetcher) -> SupabaseAccessTokenVerifier:
    return SupabaseAccessTokenVerifier(
        supabase_url="https://project.supabase.co",
        audience=AUDIENCE,
        jwks_fetcher=fetcher,
    )


def test_valid_signature_returns_typed_identity_and_uses_jwks_cache() -> None:
    fetcher = CountingJwksFetcher({"keys": [PUBLIC_JWK]})
    token_verifier = verifier(fetcher)

    first = asyncio.run(token_verifier.verify(make_token()))
    second = asyncio.run(token_verifier.verify(make_token()))

    assert first == second
    assert first.provider is AuthProvider.SUPABASE
    assert first.provider_user_id == "supabase-user-123"
    assert first.email == "player@example.com"
    assert fetcher.calls == 1


@pytest.mark.parametrize(
    "token",
    [
        make_token(private_key=OTHER_PRIVATE_KEY),
        make_token(expires_at=datetime.now(UTC) - timedelta(seconds=1)),
        make_token(issuer="https://attacker.example/auth/v1"),
        make_token(include_subject=False),
        "not-a-jwt",
    ],
)
def test_invalid_tokens_fail_closed(token: str) -> None:
    token_verifier = verifier(CountingJwksFetcher({"keys": [PUBLIC_JWK]}))

    with pytest.raises(AuthenticationError):
        asyncio.run(token_verifier.verify(token))


def test_unsupported_algorithm_fails_before_key_use() -> None:
    token = jwt.encode(
        {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": "user",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        "not-a-production-secret-that-is-long-enough-for-tests",
        algorithm="HS256",
        headers={"kid": KEY_ID},
    )
    fetcher = CountingJwksFetcher({"keys": [PUBLIC_JWK]})

    with pytest.raises(AuthenticationError):
        asyncio.run(verifier(fetcher).verify(token))

    assert fetcher.calls == 0


def test_unknown_key_id_refreshes_once_then_fails_closed() -> None:
    fetcher = CountingJwksFetcher({"keys": [PUBLIC_JWK]})

    with pytest.raises(AuthenticationError):
        asyncio.run(verifier(fetcher).verify(make_token(key_id="unknown-key")))

    assert fetcher.calls == 2


def test_jwks_failure_is_a_safe_authentication_infrastructure_error() -> None:
    async def failing_fetcher() -> Mapping[str, object]:
        request = httpx.Request("GET", "https://project.supabase.co/jwks")
        raise httpx.ConnectError("sensitive network detail", request=request)

    token_verifier = SupabaseAccessTokenVerifier(
        supabase_url="https://project.supabase.co",
        jwks_fetcher=failing_fetcher,
    )

    with pytest.raises(AuthenticationServiceError, match="verification is unavailable"):
        asyncio.run(token_verifier.verify(make_token()))
