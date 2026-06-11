"""Integration tests — IssueEligibilityValidator (REQ-29, G10)."""

from datetime import UTC, datetime

import pytest
from tests.helpers import unique_tag

from lms.api.workflows.issue_eligibility_validator import IssueEligibilityValidator
from lms.catalog.api.schemas import CatalogCreate, HoldingCreate
from lms.catalog.application.service import CatalogService
from lms.loan.api.schemas import LoanRuleSetCreate
from lms.loan.application.service import LoanService
from lms.loan.infrastructure.policy_resolver import PolicyResolver
from lms.reference.api.schemas import PatronBlockCreate, PatronCreate, PatronTypeCreate
from lms.reference.application.service import ReferenceService

pytestmark = pytest.mark.integration


def test_validator_blocked_patron_and_unpublished_holding(db_session) -> None:
    tag = unique_tag()
    loan_svc = LoanService(db_session)
    ref = ReferenceService(db_session)
    cat = CatalogService(db_session)
    validator = IssueEligibilityValidator(db_session, PolicyResolver(db_session))

    rule = loan_svc.configure_loan_rule_set(
        LoanRuleSetCreate(name=f"R-{tag}", max_active_loans=1, loan_period_days=7)
    )
    ptype = ref.create_patron_type(
        PatronTypeCreate(code=f"T_{tag}", name="T", loan_rule_set_id=rule.id)
    )
    patron = ref.register_patron(PatronCreate(display_name=f"P {tag}", patron_type_id=ptype.id))
    ref.set_patron_block(
        patron.id,
        PatronBlockCreate(reason_code="DISCIPLINE", start_at=datetime.now(UTC)),
    )

    catalog = cat.create_catalog_draft(CatalogCreate(title=f"Draft {tag}"))
    holding = cat.add_holding(
        catalog.id,
        HoldingCreate(barcode=f"B-{tag}", accession_number=f"A-{tag}"),
    )

    report = validator.validate_issue(patron.id, holding.id)
    rule_ids = {v.rule_id for v in report.violations}
    assert "REF-B2" in rule_ids
    assert "XCAT-1" in rule_ids or "CAT-5" in rule_ids
    assert not report.is_valid
