"""Integration tests — service layer with database."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from tests.helpers import unique_tag

from lms.catalog.api.schemas import CatalogCreate, HoldingCreate
from lms.catalog.application.service import CatalogService
from lms.catalog.domain.enums import CatalogingStatus, HoldingStatus
from lms.loan.api.schemas import LoanRuleSetCreate
from lms.loan.application.service import LoanService
from lms.loan.infrastructure.policy_resolver import PolicyResolver
from lms.reference.api.schemas import ClassSectionCreate, PatronCreate, PatronTypeCreate
from lms.reference.application.service import ReferenceService
from lms.shared.http.errors import AppError, ErrorCode

pytestmark = pytest.mark.integration


def test_reference_register_and_lookup_patron(db_session) -> None:
    ref = ReferenceService(db_session)
    loan = LoanService(db_session)
    tag = unique_tag()

    rule = loan.configure_loan_rule_set(
        LoanRuleSetCreate(name=f"R-{tag}", max_active_loans=2, loan_period_days=7)
    )
    ptype = ref.create_patron_type(
        PatronTypeCreate(code=f"STU_{tag}", name="Student", loan_rule_set_id=rule.id)
    )
    section = ref.create_class_section(
        ClassSectionCreate(grade="6", section="A", academic_year=f"Y-{tag}")
    )
    patron = ref.register_patron(
        PatronCreate(
            display_name="Integration Patron",
            patron_type_id=ptype.id,
            external_ref=f"EXT-{tag}",
            class_section_id=section.id,
            card_barcode=f"CARD-{tag}",
        )
    )

    assert ref.get_patron(patron.id).display_name == "Integration Patron"
    assert ref.get_patron_by_external_ref(f"EXT-{tag}").id == patron.id
    assert ref.get_patron_by_card(f"CARD-{tag}").id == patron.id

    by_card_query = ref.search_patrons(f"CARD-{tag}")
    assert len(by_card_query) == 1
    assert by_card_query[0].id == patron.id

    by_partial_name = ref.search_patrons("Integration")
    assert any(p.id == patron.id for p in by_partial_name)

    resolved = ref.resolve_patron_lookup(display_name=f"CARD-{tag}")
    assert resolved.id == patron.id


def test_reference_duplicate_external_ref_conflict(db_session) -> None:
    ref = ReferenceService(db_session)
    loan = LoanService(db_session)
    tag = unique_tag()

    rule = loan.configure_loan_rule_set(
        LoanRuleSetCreate(name=f"R-{tag}", max_active_loans=1, loan_period_days=7)
    )
    ptype = ref.create_patron_type(
        PatronTypeCreate(code=f"STU_{tag}", name="Student", loan_rule_set_id=rule.id)
    )
    ref.register_patron(
        PatronCreate(display_name="First", patron_type_id=ptype.id, external_ref=f"EXT-{tag}")
    )

    with pytest.raises(AppError) as exc:
        ref.register_patron(
            PatronCreate(display_name="Second", patron_type_id=ptype.id, external_ref=f"EXT-{tag}")
        )
    assert exc.value.code == ErrorCode.CONFLICT


def test_reference_suspend_and_block(db_session) -> None:
    ref = ReferenceService(db_session)
    loan = LoanService(db_session)
    tag = unique_tag()

    rule = loan.configure_loan_rule_set(
        LoanRuleSetCreate(name=f"R-{tag}", max_active_loans=1, loan_period_days=7)
    )
    ptype = ref.create_patron_type(
        PatronTypeCreate(code=f"STU_{tag}", name="Student", loan_rule_set_id=rule.id)
    )
    patron = ref.register_patron(PatronCreate(display_name="Blocked", patron_type_id=ptype.id))

    suspended = ref.suspend_patron(patron.id)
    assert suspended.status == "SUSPENDED"

    from lms.reference.api.schemas import PatronBlockCreate

    now = datetime.now(UTC)
    block = ref.set_patron_block(
        patron.id,
        PatronBlockCreate(reason_code="FEE_HOLD", start_at=now),
    )
    assert block.active is True
    assert ref.get_patron(patron.id).blocked is True


def test_catalog_publish_and_holding_lifecycle(db_session) -> None:
    cat_svc = CatalogService(db_session)
    tag = unique_tag()

    catalog = cat_svc.create_catalog_draft(CatalogCreate(title=f"Book {tag}", language="en"))
    assert catalog.cataloging_status == CatalogingStatus.DRAFT

    published = cat_svc.publish_catalog(catalog.id)
    assert published.cataloging_status == CatalogingStatus.PUBLISHED

    holding = cat_svc.add_holding(
        catalog.id,
        HoldingCreate(barcode=f"BC-{tag}", accession_number=f"ACC-{tag}"),
    )
    assert holding.holding_status == HoldingStatus.AVAILABLE

    results = cat_svc.search_catalog_staff(q=tag)
    assert any(c.id == catalog.id for c in results)

    withdrawn = cat_svc.withdraw_holding(holding.id)
    assert withdrawn.holding_status == HoldingStatus.WITHDRAWN


def test_catalog_cannot_withdraw_on_loan_holding(db_session) -> None:
    cat_svc = CatalogService(db_session)
    tag = unique_tag()

    catalog = cat_svc.create_catalog_draft(CatalogCreate(title=f"OnLoan {tag}"))
    cat_svc.publish_catalog(catalog.id)
    holding = cat_svc.add_holding(
        catalog.id,
        HoldingCreate(barcode=f"BC-{tag}", accession_number=f"ACC-{tag}"),
    )
    holding.holding_status = HoldingStatus.ON_LOAN
    db_session.commit()

    with pytest.raises(AppError) as exc:
        cat_svc.withdraw_holding(holding.id)
    assert exc.value.code == ErrorCode.DOMAIN_RULE_VIOLATION


def test_policy_resolver_maps_patron_type_to_rules(db_session) -> None:
    ref = ReferenceService(db_session)
    loan = LoanService(db_session)
    tag = unique_tag()

    rule = loan.configure_loan_rule_set(
        LoanRuleSetCreate(name=f"R-{tag}", max_active_loans=4, loan_period_days=10)
    )
    ptype = ref.create_patron_type(
        PatronTypeCreate(code=f"STU_{tag}", name="Student", loan_rule_set_id=rule.id)
    )

    policy = PolicyResolver(db_session).resolve(ptype.id)
    assert policy.loan_rule_set_id == rule.id
    assert policy.max_active_loans == 4
    assert policy.loan_period_days == 10
    assert policy.due_date >= datetime.now(UTC).date()


def test_loan_overdue_query(db_session) -> None:
    from lms.catalog.infrastructure.models.models import CatalogModel, HoldingModel
    from lms.loan.infrastructure.models.models import LoanModel, LoanRuleSetModel
    from lms.reference.infrastructure.models.models import PatronModel, PatronTypeModel

    tag = unique_tag()
    rule_id = uuid.uuid4()
    ptype_id = uuid.uuid4()
    patron_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    holding_id = uuid.uuid4()

    db_session.add(
        LoanRuleSetModel(id=rule_id, name=f"R-{tag}", max_active_loans=1, loan_period_days=7)
    )
    db_session.add(
        PatronTypeModel(id=ptype_id, code=f"T_{tag}", name="T", loan_rule_set_id=rule_id)
    )
    db_session.add(
        PatronModel(
            id=patron_id,
            display_name="Overdue",
            patron_type_id=ptype_id,
            status="ACTIVE",
            blocked=False,
        )
    )
    db_session.add(
        CatalogModel(id=cat_id, title=f"C-{tag}", language="en", cataloging_status="PUBLISHED")
    )
    db_session.add(
        HoldingModel(
            id=holding_id,
            catalog_id=cat_id,
            barcode=f"B-{tag}",
            accession_number=f"A-{tag}",
            holding_status="ON_LOAN",
        )
    )
    db_session.flush()
    past_due = datetime.now(UTC).date() - timedelta(days=14)
    db_session.add(
        LoanModel(
            patron_id=patron_id,
            holding_id=holding_id,
            loan_rule_set_id=rule_id,
            checkout_at=datetime.now(UTC) - timedelta(days=30),
            due_date=past_due,
        )
    )
    db_session.commit()

    overdue = LoanService(db_session).list_overdue_loans()
    assert any(row.patron_id == patron_id for row in overdue)
