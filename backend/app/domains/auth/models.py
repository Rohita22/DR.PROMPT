from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.core.exceptions import DomainError


class AuthProvider(StrEnum):
    SUPABASE = "supabase"


def _required(value: str, label: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise DomainError(f"{label} cannot be blank.")
    return normalized


def _optional_email(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    provider: AuthProvider
    provider_user_id: str
    email: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "provider_user_id",
            _required(self.provider_user_id, "Provider user ID"),
        )
        object.__setattr__(self, "email", _optional_email(self.email))


@dataclass(frozen=True, slots=True)
class ApplicationUser:
    id: str
    auth_provider: AuthProvider
    auth_provider_user_id: str
    email: str | None
    username: str | None
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _required(self.id, "User ID"))
        object.__setattr__(
            self,
            "auth_provider_user_id",
            _required(self.auth_provider_user_id, "Provider user ID"),
        )
        object.__setattr__(self, "email", _optional_email(self.email))
        if self.username is not None:
            object.__setattr__(self, "username", _required(self.username, "Username"))
        for timestamp in (self.created_at, self.updated_at):
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise DomainError("User timestamps must be timezone-aware.")
