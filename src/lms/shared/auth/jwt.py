from datetime import timedelta
from typing import cast

from fastapi_platform.jwt import AuthContext, parse_uuid
from fastapi_platform.jwt import create_access_token as _create_access_token
from fastapi_platform.jwt import decode_access_token as _decode_access_token

from lms.config import get_settings

__all__ = [
    "AuthContext",
    "create_access_token",
    "decode_access_token",
    "parse_uuid",
]


def create_access_token(
    subject: str,
    role: str,
    *,
    tenant_id: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    return cast(
        str,
        _create_access_token(
            get_settings().to_jwt_settings(),
            subject,
            role,
            tenant_id=tenant_id,
            expires_delta=expires_delta,
        ),
    )


def decode_access_token(token: str) -> AuthContext:
    return _decode_access_token(get_settings().to_jwt_settings(), token)
