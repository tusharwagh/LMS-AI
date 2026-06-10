"""Fixtures for hardening tests that require committed database state."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from lms.catalog.api.schemas import CatalogCreate, HoldingCreate
from lms.catalog.application.service import CatalogService
from lms.loan.api.schemas import LoanRuleSetCreate
from lms.loan.application.service import LoanService
from lms.reference.api.schemas import PatronCreate, PatronTypeCreate
from lms.reference.application.service import ReferenceService
from lms.shared.db.session import SessionLocal
from tests.helpers import unique_tag

pytestmark = pytest.mark.hardening


def setup_checkout_fixture(session: Session, tag: str | None = None):
    tag = tag or unique_tag()
    loan_svc = LoanService(session)
    ref = ReferenceService(session)
    cat = CatalogService(session)

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
    session.commit()
    return patron, holding, tag


@pytest.fixture
def committed_checkout_fixture():
    """Patron + available holding persisted outside the test transaction."""
    session = SessionLocal()
    try:
        patron, holding, tag = setup_checkout_fixture(session)
        yield patron, holding, tag
    finally:
        session.close()
