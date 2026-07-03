from typing import Any, cast

from sqlalchemy.orm import Session
from sqlalchemy_idempotency.service import (
    IdempotencyPayloadMismatchError,
    _payload_hash,
)
from sqlalchemy_idempotency.service import (
    find_cached_response as _find_cached_response,
)
from sqlalchemy_idempotency.service import (
    store_response as _store_response,
)

from lms.shared.idempotency.store import IdempotencyRecord

__all__ = [
    "IdempotencyPayloadMismatchError",
    "_payload_hash",
    "find_cached_response",
    "store_response",
]


def find_cached_response(
    session: Session,
    *,
    scope_key: str,
    idempotency_key: str,
    payload: dict[str, Any],
) -> tuple[int, dict[str, Any]] | None:
    return cast(
        tuple[int, dict[str, Any]] | None,
        _find_cached_response(
            session,
            IdempotencyRecord,
            scope_key=scope_key,
            idempotency_key=idempotency_key,
            payload=payload,
        ),
    )


def store_response(
    session: Session,
    *,
    scope_key: str,
    idempotency_key: str,
    payload: dict[str, Any],
    status_code: int,
    body: dict[str, Any],
) -> None:
    _store_response(
        session,
        IdempotencyRecord,
        scope_key=scope_key,
        idempotency_key=idempotency_key,
        payload=payload,
        status_code=status_code,
        body=body,
    )
