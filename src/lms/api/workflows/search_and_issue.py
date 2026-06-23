"""WF-01 — Search and issue a book (MVP.md §2.1, ADR-021)."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from lms.api.workflows.issue_eligibility_validator import IssueEligibilityValidator
from lms.catalog.application.service import CatalogService
from lms.catalog.domain.enums import CatalogingStatus, HoldingStatus
from lms.catalog.infrastructure.models.models import CatalogModel
from lms.loan.application.circulation_orchestrator import CirculationOrchestrator
from lms.loan.application.fulfillment_service import FulfillmentService
from lms.loan.domain.enums import FulfillmentMode
from lms.loan.domain.validation import ValidationReport
from lms.loan.infrastructure.models.models import CirculationFulfillmentModel, LoanModel
from lms.loan.infrastructure.policy_resolver import PolicyResolver
from lms.reference.application.service import ReferenceService
from lms.reference.infrastructure.models.models import PatronModel
from lms.shared.http.errors import AppError, ErrorCode
from lms.shared.idempotency.service import (
    IdempotencyPayloadMismatchError,
    find_cached_response,
)


@dataclass(frozen=True, slots=True)
class CatalogLendableCopy:
    holding_id: UUID
    holding_barcode: str
    catalog_title: str
    shelf_location: str | None


@dataclass(frozen=True, slots=True)
class IssueStartResult:
    patron_id: UUID
    patron_display_name: str
    patron_validation: ValidationReport
    search_results: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class IssueCommitResult:
    loan: LoanModel
    validation: ValidationReport
    fulfillment: CirculationFulfillmentModel | None


@dataclass(frozen=True, slots=True)
class IssueCancelResult:
    loan: LoanModel
    fulfillment_cancelled: bool


@dataclass(frozen=True, slots=True)
class IssueBackResult:
    target_step: int
    allowed: bool
    message: str


class SearchAndIssueWorkflow:
    def __init__(self, session: Session, orchestrator: CirculationOrchestrator) -> None:
        self._session = session
        self._orchestrator = orchestrator
        self._reference = ReferenceService(session)
        self._catalog = CatalogService(session)
        self._validator = IssueEligibilityValidator(session, PolicyResolver(session))
        self._fulfillment = FulfillmentService(session)

    def search_patrons(self, display_name: str, *, limit: int = 20) -> list[PatronModel]:
        return self._reference.search_patrons_by_name(display_name, limit=limit)

    def search_catalog_lendable(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> list[CatalogLendableCopy]:
        hits = self._catalog.search_lendable(q=query, limit=limit)
        copies: list[CatalogLendableCopy] = []
        for hit in hits:
            title = hit.catalog.title
            for holding in hit.lendable_holdings:
                copies.append(
                    CatalogLendableCopy(
                        holding_id=holding.id,
                        holding_barcode=holding.barcode,
                        catalog_title=title,
                        shelf_location=holding.shelf_location,
                    )
                )
                if len(copies) >= limit:
                    return copies
        return copies

    def start(
        self,
        *,
        patron_id: UUID | None = None,
        card_barcode: str | None = None,
        external_ref: str | None = None,
        display_name: str | None = None,
        search_query: str | None = None,
    ) -> IssueStartResult:
        patron = self._resolve_patron(
            patron_id=patron_id,
            card_barcode=card_barcode,
            external_ref=external_ref,
            display_name=display_name,
        )
        validation = self._validator.validate_patron(patron.id)
        search_results: list[dict[str, Any]] = []
        if search_query:
            hits = self._catalog.search_lendable(q=search_query)
            search_results = [
                {
                    "catalog_id": str(hit.catalog.id),
                    "title": hit.catalog.title,
                    "lendable_copies": [
                        {
                            "holding_id": str(h.id),
                            "barcode": h.barcode,
                            "accession_number": h.accession_number,
                            "shelf_location": h.shelf_location,
                        }
                        for h in hit.lendable_holdings
                    ],
                }
                for hit in hits
            ]
        return IssueStartResult(
            patron_id=patron.id,
            patron_display_name=patron.display_name,
            patron_validation=validation,
            search_results=search_results,
        )

    def find_lendable_copy_by_barcode(self, patron_id: UUID, barcode: str) -> IssueStartResult:
        patron = self._resolve_patron(
            patron_id=patron_id,
            card_barcode=None,
            external_ref=None,
            display_name=None,
        )
        validation = self._validator.validate_patron(patron.id)
        holding = self._catalog.get_holding_by_barcode(barcode)
        catalog = self._session.get(CatalogModel, holding.catalog_id)
        if catalog is None or catalog.cataloging_status != CatalogingStatus.PUBLISHED:
            raise AppError(
                ErrorCode.DOMAIN_RULE_VIOLATION,
                "Copy is not available for issue",
                status_code=422,
            )
        if holding.holding_status != HoldingStatus.AVAILABLE or not holding.circulating:
            raise AppError(
                ErrorCode.DOMAIN_RULE_VIOLATION,
                "Copy is not available for issue",
                status_code=422,
            )
        search_results = [
            {
                "catalog_id": str(catalog.id),
                "title": catalog.title,
                "lendable_copies": [
                    {
                        "holding_id": str(holding.id),
                        "barcode": holding.barcode,
                        "accession_number": holding.accession_number,
                        "shelf_location": holding.shelf_location,
                    }
                ],
            }
        ]
        return IssueStartResult(
            patron_id=patron.id,
            patron_display_name=patron.display_name,
            patron_validation=validation,
            search_results=search_results,
        )

    def validate(self, patron_id: UUID, holding_id: UUID) -> ValidationReport:
        return self._validator.validate_issue(patron_id, holding_id)

    def back_step(self, target_step: int, *, loan_id: UUID | None = None) -> IssueBackResult:
        if loan_id is not None:
            loan = self._session.get(LoanModel, loan_id)
            if loan is not None and loan.returned_at is None:
                raise AppError(
                    ErrorCode.DOMAIN_RULE_VIOLATION,
                    "Issue already committed; use cancel to roll back the loan",
                    status_code=422,
                    details={"loan_id": str(loan_id), "use": "POST /workflows/issue/cancel"},
                )
        messages = {
            1: "Patron identification — choose card, admission no., or name",
            2: "Catalog search for lendable copies",
            3: "Select a copy / scan barcode",
            4: "Choose fulfillment and commit",
        }
        return IssueBackResult(
            target_step=target_step,
            allowed=True,
            message=messages[target_step],
        )

    def cancel_issue(self, loan_id: UUID, *, idempotency_key: str) -> IssueCancelResult:
        loan = self._session.get(LoanModel, loan_id)
        if loan is None:
            raise AppError(ErrorCode.NOT_FOUND, "Loan not found", status_code=404)
        if loan.returned_at is not None:
            raise AppError(
                ErrorCode.DOMAIN_RULE_VIOLATION,
                "Loan is already closed",
                status_code=422,
            )
        fulfillment_cancelled = self._fulfillment.cancel_issue_fulfillments_for_loan(loan_id)
        returned = self._orchestrator.return_holding(
            loan_id=loan_id,
            idempotency_key=idempotency_key,
        )
        return IssueCancelResult(loan=returned, fulfillment_cancelled=fulfillment_cancelled)

    def commit(
        self,
        patron_id: UUID,
        holding_id: UUID,
        *,
        fulfillment_mode: FulfillmentMode = FulfillmentMode.DESK,
        destination_notes: str | None = None,
        destination_class_section_id: UUID | None = None,
        destination_contact: str | None = None,
        idempotency_key: str,
        operator_id: str | None = None,
    ) -> IssueCommitResult:
        checkout_payload = {
            "patron_id": str(patron_id),
            "holding_id": str(holding_id),
        }
        try:
            cached = find_cached_response(
                self._session,
                scope_key=f"checkout:{holding_id}",
                idempotency_key=idempotency_key,
                payload=checkout_payload,
            )
        except IdempotencyPayloadMismatchError as exc:
            raise AppError(
                ErrorCode.CONFLICT,
                "Idempotency key reused with different payload",
                status_code=409,
            ) from exc
        validation: ValidationReport
        if cached is None:
            validation = self._validator.validate_issue(patron_id, holding_id)
            if not validation.is_valid:
                raise AppError(
                    ErrorCode.DOMAIN_RULE_VIOLATION,
                    "Issue validation failed",
                    status_code=422,
                    details={
                        "violations": [
                            {"rule_id": v.rule_id, "message": v.message}
                            for v in validation.violations
                        ]
                    },
                )
        else:
            validation = ValidationReport()

        loan = self._orchestrator.checkout(
            patron_id,
            holding_id,
            idempotency_key=idempotency_key,
            operator_id=operator_id,
        )

        fulfillment: CirculationFulfillmentModel | None = None
        if fulfillment_mode != FulfillmentMode.DESK:
            if cached is not None:
                fulfillment = self._fulfillment.get_issue_fulfillment_for_loan(loan.id)
            else:
                fulfillment = self._fulfillment.create_issue_fulfillment(
                    loan_id=loan.id,
                    holding_id=holding_id,
                    mode=fulfillment_mode,
                    destination_notes=destination_notes,
                    destination_class_section_id=destination_class_section_id,
                    destination_contact=destination_contact,
                )
                self._session.commit()
                self._session.refresh(fulfillment)

        return IssueCommitResult(loan=loan, validation=validation, fulfillment=fulfillment)

    def _resolve_patron(
        self,
        *,
        patron_id: UUID | None,
        card_barcode: str | None,
        external_ref: str | None,
        display_name: str | None,
    ) -> PatronModel:
        if patron_id is not None:
            return self._reference.get_patron(patron_id)
        if card_barcode is not None:
            return self._reference.get_patron_by_card(card_barcode)
        if external_ref is not None:
            return self._reference.get_patron_by_external_ref(external_ref)
        if display_name is not None:
            matches = self._reference.search_patrons_by_name(display_name, limit=2)
            if not matches:
                raise AppError(
                    ErrorCode.NOT_FOUND,
                    "No patron found matching that name",
                    status_code=404,
                )
            if len(matches) > 1:
                raise AppError(
                    ErrorCode.CONFLICT,
                    "Multiple patrons match that name; use search-patrons and select patron_id",
                    status_code=409,
                    details={
                        "patrons": [
                            {
                                "id": str(p.id),
                                "display_name": p.display_name,
                                "external_ref": p.external_ref,
                                "card_barcode": p.card_barcode,
                            }
                            for p in self._reference.search_patrons_by_name(display_name, limit=20)
                        ]
                    },
                )
            return matches[0]
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "One of patron_id, card_barcode, external_ref, or display_name is required",
            status_code=422,
        )
