"""Seed default API users for development and tests."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from lms.shared.auth.password import hash_password
from lms.shared.auth.roles import Role
from lms.shared.infrastructure.models.api_user import ApiUserModel

USER_ADMIN = uuid.UUID("00000000-0001-4001-8001-000000000001")
USER_LIBRARIAN = uuid.UUID("00000000-0001-4001-8001-000000000002")
USER_PATRON = uuid.UUID("00000000-0001-4001-8001-000000000003")

DEFAULT_DEV_PASSWORD = "changeme"


def ensure_default_api_users(session: Session, *, password: str = DEFAULT_DEV_PASSWORD) -> None:
    defaults = (
        (USER_ADMIN, "admin", Role.ADMIN, "Library Admin"),
        (USER_LIBRARIAN, "librarian", Role.LIBRARIAN, "Desk Librarian"),
        (USER_PATRON, "patron", Role.PATRON, "Sample Patron"),
    )
    pwd_hash = hash_password(password)
    for user_id, username, role, display_name in defaults:
        existing = session.scalar(
            select(ApiUserModel).where(ApiUserModel.username == username)
        )
        if existing is not None:
            continue
        session.add(
            ApiUserModel(
                id=user_id,
                username=username,
                password_hash=pwd_hash,
                role=role.value,
                display_name=display_name,
                active=True,
            )
        )
