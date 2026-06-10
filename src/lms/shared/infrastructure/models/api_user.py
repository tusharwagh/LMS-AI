from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from lms.shared.db.base import Base
from lms.shared.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ApiUserModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "api_users"

    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
