from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from lms.api.openapi import BEARER_SCHEME_NAME
from lms.shared.auth.jwt import AuthContext, decode_access_token
from lms.shared.auth.roles import Role
from lms.shared.db.deps import get_db

# Swagger Authorize → paste JWT (access_token from POST /api/v1/auth/token).
http_bearer = HTTPBearer(
    scheme_name=BEARER_SCHEME_NAME,
    bearerFormat="JWT",
    description="Paste access_token from POST /api/v1/auth/token",
    auto_error=False,
)

DbSession = Annotated[Session, Depends(get_db)]


def get_auth_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(http_bearer)],
) -> AuthContext | None:
    if credentials is None:
        return None
    try:
        return decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": str(exc)},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_auth(
    ctx: Annotated[AuthContext | None, Depends(get_auth_context)],
) -> AuthContext:
    if ctx is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Authentication required"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return ctx


def require_roles(*allowed: Role):
    allowed_set = frozenset(allowed)

    def _checker(ctx: Annotated[AuthContext, Depends(require_auth)]) -> AuthContext:
        if ctx.role not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Insufficient role"},
            )
        return ctx

    return _checker
