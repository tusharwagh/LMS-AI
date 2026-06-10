"""Composes domain ports into ValidationReport for desk issue preview (REQ-29)."""

from uuid import UUID

from sqlalchemy.orm import Session

from lms.catalog.domain.enums import CatalogingStatus, HoldingStatus
from lms.catalog.infrastructure.models.models import CatalogModel, HoldingModel
from lms.loan.domain.ports import PolicyResolverPort
from lms.loan.domain.validation import ValidationReport
from lms.loan.infrastructure.policy_resolver import PolicyResolver
from lms.reference.infrastructure.adapters.patron_eligibility import PatronEligibilityAdapter


class IssueEligibilityValidator:
    def __init__(
        self,
        session: Session,
        policy_resolver: PolicyResolverPort | None = None,
    ) -> None:
        self._session = session
        self._patron_eligibility = PatronEligibilityAdapter(session)
        self._policy_resolver = policy_resolver or PolicyResolver(session)

    def validate_patron(self, patron_id: UUID) -> ValidationReport:
        report = ValidationReport()
        try:
            eligibility = self._patron_eligibility.check(patron_id)
        except ValueError:
            report.add("REF-P6", "Patron not found")
            return report

        if not eligibility.is_active:
            report.add("REF-P6", "Patron is not active")
        if eligibility.is_blocked:
            report.add("REF-B2", "Patron is blocked from borrowing")

        try:
            policy = self._policy_resolver.resolve(eligibility.patron_type_id)
        except ValueError:
            report.add("LN-R1", "No loan rule set mapped for patron type")
            return report

        if eligibility.open_loan_count >= policy.max_active_loans:
            report.add(
                "LN-R2",
                f"Patron has reached maximum active loans ({policy.max_active_loans})",
            )
        return report

    def validate_issue(self, patron_id: UUID, holding_id: UUID) -> ValidationReport:
        report = self.validate_patron(patron_id)
        holding_report = self._validate_holding(holding_id)
        report.violations.extend(holding_report.violations)
        return report

    def preview_holding(self, holding_id: UUID) -> ValidationReport:
        return self._validate_holding(holding_id)

    def _validate_holding(self, holding_id: UUID) -> ValidationReport:
        report = ValidationReport()
        holding = self._session.get(HoldingModel, holding_id)
        if holding is None:
            report.add("LN-H1", "Holding not found")
            return report

        catalog = self._session.get(CatalogModel, holding.catalog_id)
        if catalog is None:
            report.add("CAT-5", "Catalog record not found for holding")
            return report

        if catalog.cataloging_status != CatalogingStatus.PUBLISHED:
            report.add("XCAT-1", "Catalog record is not published")
            report.add("CAT-5", "Only published catalog records may be issued")

        if not holding.circulating:
            report.add("HLD-4", "Holding is not marked as circulating")

        if holding.holding_status != HoldingStatus.AVAILABLE:
            report.add(
                "HLD-5",
                f"Holding is not available (status: {holding.holding_status})",
            )
        return report
