from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from jose import JWTError, jwt

from lms.config import get_settings
from lms.shared.auth.roles import Role


@dataclass(frozen=True, slots=True)
class AuthContext:
    subject: str
    role: Role
    tenant_id: str | None = None


def create_access_token(
    subject: str,
    role: Role,
    *,
    tenant_id: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role.value,
        "exp": expire,
    }
    if tenant_id is not None:
        payload["tenant_id"] = tenant_id
    return jwt.encode(payload, settings.app_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> AuthContext:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.app_secret_key, algorithms=[settings.jwt_algorithm])
        subject = payload.get("sub")
        role_raw = payload.get("role")
        if not subject or not role_raw:
            raise JWTError("Missing claims")
        return AuthContext(
            subject=str(subject),
            role=Role(role_raw),
            tenant_id=payload.get("tenant_id"),
        )
    except JWTError as exc:
        raise ValueError("Invalid token") from exc


def parse_uuid(value: str) -> UUID:
    return UUID(value)
