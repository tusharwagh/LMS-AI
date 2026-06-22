from sqlalchemy import select
from sqlalchemy.orm import Session

from lms.api.errors import AppError, ErrorCode
from lms.config import get_settings
from lms.platform.auth.roles import Role
from lms.platform.infrastructure.models.api_user import ApiUserModel
from lms.shared.auth.jwt import create_access_token
from lms.shared.auth.password import verify_password


class AuthService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def authenticate(self, username: str, password: str) -> ApiUserModel:
        row = self._session.scalar(
            select(ApiUserModel).where(ApiUserModel.username == username.strip().lower())
        )
        if row is None or not row.active:
            raise AppError(
                ErrorCode.UNAUTHORIZED,
                "Invalid username or password",
                status_code=401,
            )
        if not verify_password(password, row.password_hash):
            raise AppError(
                ErrorCode.UNAUTHORIZED,
                "Invalid username or password",
                status_code=401,
            )
        return row

    def issue_access_token(self, user: ApiUserModel) -> tuple[str, int]:
        settings = get_settings()
        token = create_access_token(
            str(user.id),
            Role(user.role).value,
            tenant_id=user.tenant_id,
        )
        return token, settings.jwt_access_token_expire_minutes * 60

    def get_user(self, user_id: str) -> ApiUserModel:
        from uuid import UUID

        try:
            uid = UUID(user_id)
        except ValueError as exc:
            raise AppError(ErrorCode.NOT_FOUND, "User not found", status_code=404) from exc
        row = self._session.get(ApiUserModel, uid)
        if row is None or not row.active:
            raise AppError(ErrorCode.NOT_FOUND, "User not found", status_code=404)
        return row
