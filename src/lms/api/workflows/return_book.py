"""WF-02 — Return a book (MVP.md §2.1, ADR-021)."""

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from lms.api.errors import AppError, ErrorCode
from lms.catalog.application.service import CatalogService
from lms.catalog.infrastructure.models.models import CatalogModel, HoldingModel
from lms.loan.application.circulation_orchestrator import CirculationOrchestrator
from lms.loan.application.fulfillment_service import FulfillmentService
from lms.loan.application.service import LoanService
from lms.loan.domain.enums import FulfillmentDirection, FulfillmentStatus
from lms.loan.infrastructure.models.models import CirculationFulfillmentModel, LoanModel
from lms.reference.application.service import ReferenceService
from lms.shared.time import library_today


@dataclass(frozen=True, slots=True)
class ReturnStartResult:
    loan_id: UUID
    holding_id: UUID
    holding_barcode: str
    patron_id: UUID
    patron_display_name: str
    catalog_title: str
    due_date: date
    is_overdue: bool
    open_loans_for_patron: int


@dataclass(frozen=True, slots=True)
class ReturnCommitResult:
    loan: LoanModel
    fulfillment: CirculationFulfillmentModel | None = None


class ReturnBookWorkflow:
    def __init__(self, session: Session, orchestrator: CirculationOrchestrator) -> None:
        self._session = session
        self._orchestrator = orchestrator
        self._loan_service = LoanService(session)
        self._catalog = CatalogService(session)
        self._reference = ReferenceService(session)
        self._fulfillment = FulfillmentService(session)

    def start(
        self,
        *,
        barcode: str | None = None,
        loan_id: UUID | None = None,
    ) -> ReturnStartResult:
        loan, holding = self._resolve_loan(barcode=barcode, loan_id=loan_id)
        patron = self._reference.get_patron(loan.patron_id)
        catalog = self._session.get(CatalogModel, holding.catalog_id)
        title = catalog.title if catalog else "Unknown title"
        today = library_today()
        open_loans = self._loan_service.list_open_loans_by_patron(loan.patron_id)
        return ReturnStartResult(
            loan_id=loan.id,
            holding_id=holding.id,
            holding_barcode=holding.barcode,
            patron_id=loan.patron_id,
            patron_display_name=patron.display_name,
            catalog_title=title,
            due_date=loan.due_date,
            is_overdue=loan.due_date < today,
            open_loans_for_patron=len(open_loans),
        )

    def commit_desk(
        self,
        *,
        holding_id: UUID | None = None,
        loan_id: UUID | None = None,
        idempotency_key: str,
    ) -> ReturnCommitResult:
        loan = self._orchestrator.return_holding(
            holding_id=holding_id,
            loan_id=loan_id,
            idempotency_key=idempotency_key,
        )
        return ReturnCommitResult(loan=loan)

    def initiate_pickup(
        self,
        loan_id: UUID,
        *,
        destination_notes: str | None = None,
        destination_class_section_id: UUID | None = None,
        destination_contact: str | None = None,
    ) -> CirculationFulfillmentModel:
        fulfillment = self._fulfillment.initiate_return_pickup(
            loan_id=loan_id,
            destination_notes=destination_notes,
            destination_class_section_id=destination_class_section_id,
            destination_contact=destination_contact,
        )
        self._session.commit()
        self._session.refresh(fulfillment)
        return fulfillment

    def confirm_pickup_received(
        self,
        fulfillment_id: UUID,
        *,
        idempotency_key: str,
    ) -> ReturnCommitResult:
        fulfillment = self._fulfillment.get_fulfillment(fulfillment_id)
        if fulfillment.direction != FulfillmentDirection.RETURN:
            raise AppError(
                ErrorCode.DOMAIN_RULE_VIOLATION,
                "Fulfillment is not a return pick-up",
                status_code=422,
            )
        if fulfillment.loan_id is None:
            raise AppError(
                ErrorCode.DOMAIN_RULE_VIOLATION,
                "Return fulfillment has no linked loan",
                status_code=422,
            )

        loan_check = self._session.get(LoanModel, fulfillment.loan_id)
        if loan_check is not None and loan_check.returned_at is not None:
            return ReturnCommitResult(loan=loan_check, fulfillment=fulfillment)

        if fulfillment.status != FulfillmentStatus.COMPLETED:
            fulfillment.status = FulfillmentStatus.COMPLETED
            self._session.flush()

        loan = self._orchestrator.return_holding(
            loan_id=fulfillment.loan_id,
            idempotency_key=idempotency_key,
        )
        self._session.refresh(fulfillment)
        return ReturnCommitResult(loan=loan, fulfillment=fulfillment)

    def _resolve_loan(
        self,
        *,
        barcode: str | None,
        loan_id: UUID | None,
    ) -> tuple[LoanModel, HoldingModel]:
        if barcode is not None:
            holding = self._catalog.get_holding_by_barcode(barcode)
            loan = self._loan_service.get_open_loan_by_holding(holding.id)
            return loan, holding

        if loan_id is not None:
            loan = self._session.get(LoanModel, loan_id)
            if loan is None:
                raise AppError(ErrorCode.NOT_FOUND, "Loan not found", status_code=404)
            if loan.returned_at is not None:
                raise AppError(ErrorCode.NOT_FOUND, "Loan is already closed", status_code=404)
            holding = self._session.get(HoldingModel, loan.holding_id)
            if holding is None:
                raise AppError(ErrorCode.NOT_FOUND, "Holding not found", status_code=404)
            return loan, holding

        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "Either barcode or loan_id is required",
            status_code=422,
        )
