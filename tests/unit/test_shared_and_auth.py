"""Unit tests — no database required."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from lms.api.errors import AppError, ErrorCode, error_body
from lms.reference.application.service import ReferenceService
from lms.reference.infrastructure.models.models import PatronBlockModel
from lms.shared.auth.jwt import create_access_token, decode_access_token
from lms.shared.auth.roles import Role
from lms.shared.idempotency.service import _payload_hash, find_cached_response, store_response

pytestmark = pytest.mark.unit


def test_payload_hash_stable_for_same_payload() -> None:
    payload = {"patron_id": "abc", "holding_id": "def"}
    assert _payload_hash(payload) == _payload_hash(payload)


def test_payload_hash_differs_when_payload_changes() -> None:
    a = {"patron_id": "abc"}
    b = {"patron_id": "xyz"}
    assert _payload_hash(a) != _payload_hash(b)


def test_error_body_shape() -> None:
    body = error_body(ErrorCode.NOT_FOUND, "missing", retriable=True, details={"id": "1"})
    assert body == {
        "code": "NOT_FOUND",
        "message": "missing",
        "retriable": True,
        "details": {"id": "1"},
    }


def test_app_error_attributes() -> None:
    err = AppError(ErrorCode.CONFLICT, "dup", status_code=409)
    assert err.code == ErrorCode.CONFLICT
    assert err.status_code == 409
    assert str(err) == "dup"


def test_jwt_round_trip() -> None:
    token = create_access_token("lib-1", Role.LIBRARIAN, tenant_id="school-a")
    ctx = decode_access_token(token)
    assert ctx.subject == "lib-1"
    assert ctx.role == Role.LIBRARIAN
    assert ctx.tenant_id == "school-a"


def test_jwt_rejects_invalid_token() -> None:
    with pytest.raises(ValueError, match="Invalid token"):
        decode_access_token("not-a-jwt")


def test_password_hash_round_trip() -> None:
    from lms.shared.auth.password import hash_password, verify_password

    hashed = hash_password("secret-pass")
    assert verify_password("secret-pass", hashed)
    assert not verify_password("wrong", hashed)


@pytest.mark.parametrize(
    ("active", "start_offset", "end_offset", "now_offset", "expected"),
    [
        (False, 0, None, 0, False),
        (True, -1, 1, 0, True),
        (True, 1, None, 0, False),
        (True, -2, -1, 0, False),
    ],
)
def test_patron_blocked_window(
    active: bool,
    start_offset: int,
    end_offset: int | None,
    now_offset: int,
    expected: bool,
) -> None:
    now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    block = PatronBlockModel(
        patron_id=uuid.uuid4(),
        reason_code="TEST",
        active=active,
        start_at=now + timedelta(days=start_offset),
        end_at=(now + timedelta(days=end_offset)) if end_offset is not None else None,
    )
    assert (
        ReferenceService.is_patron_blocked_now(block, now + timedelta(days=now_offset)) is expected
    )


class _FakeQuery:
    def __init__(self, row) -> None:
        self._row = row

    def filter_by(self, **_kwargs) -> _FakeQuery:
        return self

    def one_or_none(self):
        return self._row


class _FakeSession:
    def __init__(self, row) -> None:
        self._row = row
        self.added = []

    def query(self, _model) -> _FakeQuery:
        return _FakeQuery(self._row)

    def add(self, obj) -> None:
        self.added.append(obj)


def test_idempotency_cache_miss() -> None:
    session = _FakeSession(None)
    assert (
        find_cached_response(
            session,  # type: ignore[arg-type]
            scope_key="checkout:x",
            idempotency_key="key-1",
            payload={"a": 1},
        )
        is None
    )


def test_idempotency_cache_hit() -> None:
    payload = {"a": 1}
    from lms.shared.idempotency.store import IdempotencyRecord

    row = IdempotencyRecord(
        scope_key="checkout:x",
        idempotency_key="key-1",
        payload_hash=_payload_hash(payload),
        response_status=201,
        response_body='{"id": "loan-1"}',
        expires_at=datetime.now(UTC),
    )
    session = _FakeSession(row)
    result = find_cached_response(
        session,  # type: ignore[arg-type]
        scope_key="checkout:x",
        idempotency_key="key-1",
        payload=payload,
    )
    assert result == (201, {"id": "loan-1"})


def test_idempotency_hash_mismatch_returns_none() -> None:
    from lms.shared.idempotency.store import IdempotencyRecord

    row = IdempotencyRecord(
        scope_key="checkout:x",
        idempotency_key="key-1",
        payload_hash="deadbeef",
        response_status=201,
        response_body="{}",
        expires_at=datetime.now(UTC),
    )
    session = _FakeSession(row)
    assert (
        find_cached_response(
            session,  # type: ignore[arg-type]
            scope_key="checkout:x",
            idempotency_key="key-1",
            payload={"different": True},
        )
        is None
    )


def test_store_response_adds_record() -> None:
    session = _FakeSession(None)
    store_response(
        session,  # type: ignore[arg-type]
        scope_key="return:y",
        idempotency_key="key-2",
        payload={"holding_id": "h1"},
        status_code=200,
        body={"id": "loan-1"},
    )
    assert len(session.added) == 1
