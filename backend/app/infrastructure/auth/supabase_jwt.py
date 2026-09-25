import asyncio
from collections.abc import Awaitable, Callable, Mapping
from time import monotonic
from typing import cast

import httpx
import jwt
from jwt import PyJWK
from jwt.exceptions import InvalidTokenError

from app.core.exceptions import AuthenticationError, AuthenticationServiceError
from app.domains.auth import AuthenticatedIdentity, AuthProvider

type JwksDocument = Mapping[str, object]
type JwksFetcher = Callable[[], Awaitable[JwksDocument]]


class SupabaseAccessTokenVerifier:
    """Verify Supabase access tokens against cached asymmetric public keys."""

    def __init__(
        self,
        *,
        supabase_url: str,
        audience: str = "authenticated",
        allowed_algorithms: frozenset[str] = frozenset({"RS256", "ES256"}),
        cache_ttl_seconds: int = 600,
        request_timeout_seconds: float = 5.0,
        jwks_fetcher: JwksFetcher | None = None,
    ) -> None:
        base_url = supabase_url.rstrip("/")
        self._issuer = f"{base_url}/auth/v1"
        self._jwks_url = f"{self._issuer}/.well-known/jwks.json"
        self._audience = audience
        self._allowed_algorithms = allowed_algorithms
        self._cache_ttl_seconds = cache_ttl_seconds
        self._request_timeout_seconds = request_timeout_seconds
        self._jwks_fetcher = jwks_fetcher or self._fetch_jwks
        self._cached_keys: tuple[Mapping[str, object], ...] | None = None
        self._cache_expires_at = 0.0
        self._cache_lock = asyncio.Lock()

    async def verify(self, access_token: str) -> AuthenticatedIdentity:
        if not access_token.strip():
            raise AuthenticationError()
        try:
            header = jwt.get_unverified_header(access_token)
        except InvalidTokenError:
            raise AuthenticationError() from None

        algorithm = header.get("alg")
        key_id = header.get("kid")
        if algorithm not in self._allowed_algorithms or not isinstance(key_id, str) or not key_id:
            raise AuthenticationError()

        key = await self._find_signing_key(key_id, algorithm)
        try:
            claims = jwt.decode(
                access_token,
                key=key.key,
                algorithms=[algorithm],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iss", "sub"]},
            )
        except InvalidTokenError:
            raise AuthenticationError() from None

        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            raise AuthenticationError()
        email_claim = claims.get("email")
        email = email_claim if isinstance(email_claim, str) else None
        return AuthenticatedIdentity(
            provider=AuthProvider.SUPABASE,
            provider_user_id=subject,
            email=email,
        )

    async def _find_signing_key(self, key_id: str, algorithm: str) -> PyJWK:
        keys = await self._get_keys()
        matching = self._matching_key(keys, key_id, algorithm)
        if matching is None:
            keys = await self._get_keys(force_refresh=True)
            matching = self._matching_key(keys, key_id, algorithm)
        if matching is None:
            raise AuthenticationError()
        try:
            return PyJWK.from_dict(dict(matching))
        except (InvalidTokenError, ValueError, TypeError):
            raise AuthenticationError() from None

    @staticmethod
    def _matching_key(
        keys: tuple[Mapping[str, object], ...],
        key_id: str,
        algorithm: str,
    ) -> Mapping[str, object] | None:
        for key in keys:
            if key.get("kid") != key_id:
                continue
            key_algorithm = key.get("alg")
            if key_algorithm is not None and key_algorithm != algorithm:
                continue
            return key
        return None

    async def _get_keys(
        self,
        *,
        force_refresh: bool = False,
    ) -> tuple[Mapping[str, object], ...]:
        now = monotonic()
        if not force_refresh and self._cached_keys is not None and now < self._cache_expires_at:
            return self._cached_keys

        async with self._cache_lock:
            now = monotonic()
            if not force_refresh and self._cached_keys is not None and now < self._cache_expires_at:
                return self._cached_keys
            try:
                document = await self._jwks_fetcher()
                raw_keys = document.get("keys")
                if not isinstance(raw_keys, list) or not raw_keys:
                    raise ValueError("JWKS has no keys")
                keys = tuple(
                    cast(Mapping[str, object], key) for key in raw_keys if isinstance(key, Mapping)
                )
                if not keys:
                    raise ValueError("JWKS has no usable keys")
            except AuthenticationServiceError:
                raise
            except (httpx.HTTPError, ValueError, TypeError):
                raise AuthenticationServiceError() from None
            self._cached_keys = keys
            self._cache_expires_at = now + self._cache_ttl_seconds
            return keys

    async def _fetch_jwks(self) -> JwksDocument:
        try:
            async with httpx.AsyncClient(timeout=self._request_timeout_seconds) as client:
                response = await client.get(self._jwks_url)
                response.raise_for_status()
                document = response.json()
        except (httpx.HTTPError, ValueError):
            raise AuthenticationServiceError() from None
        if not isinstance(document, Mapping):
            raise AuthenticationServiceError()
        return cast(JwksDocument, document)
