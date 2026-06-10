import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from lms.shared.idempotency.store import IDEMPOTENCY_TTL, IdempotencyRecord


def _payload_hash(payload: dict[str, Any]) -> str:
    normalized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode()).hexdigest()


def find_cached_response(
    session: Session,
    *,
    scope_key: str,
    idempotency_key: str,
    payload: dict[str, Any],
) -> tuple[int, dict[str, Any]] | None:
    row = (
        session.query(IdempotencyRecord)
        .filter_by(scope_key=scope_key, idempotency_key=idempotency_key)
        .one_or_none()
    )
    if row is None:
        return None
    if row.payload_hash != _payload_hash(payload):
        return None
    return row.response_status, json.loads(row.response_body)


def store_response(
    session: Session,
    *,
    scope_key: str,
    idempotency_key: str,
    payload: dict[str, Any],
    status_code: int,
    body: dict[str, Any],
) -> None:
    from datetime import UTC, datetime

    session.add(
        IdempotencyRecord(
            scope_key=scope_key,
            idempotency_key=idempotency_key,
            payload_hash=_payload_hash(payload),
            response_status=status_code,
            response_body=json.dumps(body),
            expires_at=datetime.now(UTC) + IDEMPOTENCY_TTL,
        )
    )
