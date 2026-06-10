"""Integration tests — circulation orchestrator with real database."""

import uuid
from datetime import UTC, datetime

import pytest

from lms.api.composition import _build_orchestrator
from lms.catalog.api.schemas import CatalogCreate, HoldingCreate
from lms.catalog.application.service import CatalogService
from lms.catalog.domain.enums import HoldingStatus
from lms.loan.api.schemas import LoanRuleSetCreate
from lms.loan.application.service import LoanService
from lms.reference.api.schemas import PatronCreate, PatronTypeCreate
from lms.reference.application.service import ReferenceService
from tests.helpers import unique_tag

pytestmark = pytest.mark.integration


def _setup_checkout_fixture(db_session, tag: str):
    loan_svc = LoanService(db_session)
    ref = ReferenceService(db_session)
    cat = CatalogService(db_session)

    rule = loan_svc.configure_loan_rule_set(
        LoanRuleSetCreate(name=f"R-{tag}", max_active_loans=2, loan_period_days=14)
    )
    ptype = ref.create_patron_type(
        PatronTypeCreate(code=f"STU_{tag}", name="Student", loan_rule_set_id=rule.id)
    )
    patron = ref.register_patron(
        PatronCreate(display_name=f"Patron {tag}", patron_type_id=ptype.id)
    )
    catalog = cat.create_catalog_draft(CatalogCreate(title=f"Title {tag}"))
    cat.publish_catalog(catalog.id)
    holding = cat.add_holding(
        catalog.id,
        HoldingCreate(barcode=f"BC-{tag}", accession_number=f"ACC-{tag}"),
    )
    return patron, holding, rule


def test_orchestrator_checkout_and_return(db_session) -> None:
    tag = unique_tag()
    patron, holding, _rule = _setup_checkout_fixture(db_session, tag)
    orchestrator = _build_orchestrator(db_session)

    loan = orchestrator.checkout(
        patron.id,
        holding.id,
        idempotency_key=f"chk-{tag}",
        operator_id="test-lib",
    )
    assert loan.returned_at is None
    assert loan.patron_id == patron.id
    assert loan.holding_id == holding.id

    db_session.refresh(holding)
    assert holding.holding_status == HoldingStatus.ON_LOAN

    returned = orchestrator.return_holding(
        holding_id=holding.id,
        idempotency_key=f"ret-{tag}",
    )
    assert returned.id == loan.id
    assert returned.returned_at is not None

    db_session.refresh(holding)
    assert holding.holding_status == HoldingStatus.AVAILABLE


def test_orchestrator_checkout_idempotent(db_session) -> None:
    tag = unique_tag()
    patron, holding, _ = _setup_checkout_fixture(db_session, tag)
    orchestrator = _build_orchestrator(db_session)
    key = f"idempotent-{tag}"

    first = orchestrator.checkout(patron.id, holding.id, idempotency_key=key)
    second = orchestrator.checkout(patron.id, holding.id, idempotency_key=key)
    assert second.id == first.id


def test_orchestrator_rejects_max_active_loans(db_session) -> None:
    tag = unique_tag()
    loan_svc = LoanService(db_session)
    ref = ReferenceService(db_session)
    cat = CatalogService(db_session)

    rule = loan_svc.configure_loan_rule_set(
        LoanRuleSetCreate(name=f"R-{tag}", max_active_loans=1, loan_period_days=7)
    )
    ptype = ref.create_patron_type(
        PatronTypeCreate(code=f"STU_{tag}", name="Student", loan_rule_set_id=rule.id)
    )
    patron = ref.register_patron(
        PatronCreate(display_name=f"Patron {tag}", patron_type_id=ptype.id)
    )

    def add_holding(suffix: str):
        catalog = cat.create_catalog_draft(CatalogCreate(title=f"T-{suffix}"))
        cat.publish_catalog(catalog.id)
        return cat.add_holding(
            catalog.id,
            HoldingCreate(barcode=f"B-{suffix}", accession_number=f"A-{suffix}"),
        )

    h1 = add_holding(f"{tag}-1")
    h2 = add_holding(f"{tag}-2")
    orchestrator = _build_orchestrator(db_session)

    orchestrator.checkout(patron.id, h1.id, idempotency_key=f"k1-{tag}")

    from lms.api.errors import AppError

    with pytest.raises(AppError) as exc:
        orchestrator.checkout(patron.id, h2.id, idempotency_key=f"k2-{tag}")
    assert exc.value.status_code == 422
