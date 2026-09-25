from functools import lru_cache

from app.core.config import Settings
from app.core.exceptions import AuthenticationServiceError
from app.domains.auth import AccessTokenVerifier
from app.infrastructure.auth.supabase_jwt import SupabaseAccessTokenVerifier


@lru_cache
def _cached_verifier(
    supabase_url: str,
    audience: str,
    cache_ttl_seconds: int,
    timeout_seconds: float,
) -> SupabaseAccessTokenVerifier:
    return SupabaseAccessTokenVerifier(
        supabase_url=supabase_url,
        audience=audience,
        cache_ttl_seconds=cache_ttl_seconds,
        request_timeout_seconds=timeout_seconds,
    )


def create_access_token_verifier(settings: Settings) -> AccessTokenVerifier:
    if settings.supabase_url is None:
        raise AuthenticationServiceError("Authentication configuration is unavailable.")
    return _cached_verifier(
        str(settings.supabase_url).rstrip("/"),
        settings.supabase_jwt_audience,
        settings.supabase_jwks_cache_seconds,
        settings.supabase_jwks_timeout_seconds,
    )
