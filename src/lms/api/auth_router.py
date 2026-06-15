from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from lms.api.auth_schemas import TokenResponse, UserResponse
from lms.api.deps import DbSession, require_auth
from lms.shared.application.auth_service import AuthService
from lms.shared.auth.jwt import AuthContext
from lms.shared.auth.roles import Role

router = APIRouter()


def _auth_service(session: DbSession) -> AuthService:
    return AuthService(session)


@router.post("/token", response_model=TokenResponse)
def login_for_access_token(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: Annotated[AuthService, Depends(_auth_service)],
) -> TokenResponse:
    user = service.authenticate(form.username, form.password)
    access_token, expires_in = service.issue_access_token(user)
    return TokenResponse(access_token=access_token, expires_in=expires_in)


@router.get("/me", response_model=UserResponse)
def read_current_user(
    auth: Annotated[AuthContext, Depends(require_auth)],
    service: Annotated[AuthService, Depends(_auth_service)],
) -> UserResponse:
    user = service.get_user(auth.subject)
    return UserResponse(
        id=str(user.id),
        username=user.username,
        role=Role(user.role),
        display_name=user.display_name,
        tenant_id=user.tenant_id,
    )
