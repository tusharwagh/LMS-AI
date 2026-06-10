"""G2 — concurrent checkout on the same holding (MVP.md §13.2)."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from lms.api.composition import _build_orchestrator
from lms.api.errors import AppError
from lms.shared.db.session import SessionLocal
from tests.hardening.conftest import setup_checkout_fixture

pytestmark = [pytest.mark.hardening, pytest.mark.integration]


def _attempt_checkout(patron_id, holding_id, key: str) -> tuple[str, int | str]:
    session = SessionLocal()
    try:
        orchestrator = _build_orchestrator(session)
        loan = orchestrator.checkout(
            patron_id,
            holding_id,
            idempotency_key=key,
            operator_id="concurrency-test",
        )
        return "ok", str(loan.id)
    except AppError as exc:
        return "err", exc.status_code
    finally:
        session.close()


def test_concurrent_checkout_same_holding_one_winner() -> None:
    """Two simultaneous checkouts on one holding — exactly one succeeds (REQ-24, G2)."""
    setup = SessionLocal()
    try:
        patron, holding, tag = setup_checkout_fixture(setup)
    finally:
        setup.close()

    keys = [f"conc-a-{tag}-{uuid.uuid4().hex[:8]}", f"conc-b-{tag}-{uuid.uuid4().hex[:8]}"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda key: _attempt_checkout(patron.id, holding.id, key),
                keys,
            )
        )

    successes = [r for r in results if r[0] == "ok"]
    failures = [r for r in results if r[0] == "err"]
    assert len(successes) == 1
    assert len(failures) == 1
    assert failures[0][1] == 422

    verify = SessionLocal()
    try:
        from sqlalchemy import select

        from lms.loan.infrastructure.models.models import LoanModel

        open_loans = list(
            verify.scalars(
                select(LoanModel).where(
                    LoanModel.holding_id == holding.id,
                    LoanModel.returned_at.is_(None),
                )
            )
        )
        assert len(open_loans) == 1
        assert str(open_loans[0].id) == successes[0][1]
    finally:
        verify.close()
