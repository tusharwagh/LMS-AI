from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from lms.shared.auth.jwt import AuthContext, decode_access_token
from lms.shared.auth.roles import Role

_bearer = HTTPBearer(auto_error=False)


def get_auth_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AuthContext | None:
    if credentials is None:
        return None
    try:
        return decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": str(exc)},
        ) from exc


def require_auth(
    ctx: Annotated[AuthContext | None, Depends(get_auth_context)],
) -> AuthContext:
    if ctx is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Authentication required"},
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
